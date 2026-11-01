import logging
from datetime import datetime, date, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload

from backend.app.database import get_db
from backend.app.auth.dependencies import get_current_user, require_role
from backend.app.models.user import User, UserRole
from backend.app.models.institution import Institution
from backend.app.models.deposit import Deposit, DepositStatus
from backend.app.models.contract import Contract
from backend.app.models.approval_request import ApprovalRequest, RequestType, RequestStatus
from backend.app.models.audit_log import AuditLog
from backend.app.models.notification import Notification
from backend.app.services.audit_service import record_audit_log
from backend.app.utils.clock import utc_now
from backend.app.schemas.approval_request import (
    RenewalRequestCreate,
    ReleaseRequestCreate,
    ForfeitureRequestCreate,
    AssignOfficerRequest,
    ApprovalDecisionRequest,
    RejectionDecisionRequest,
    ApprovalRequestResponse,
)

logger = logging.getLogger("aicte_fdr.approval_requests")

router = APIRouter(prefix="/requests", tags=["Approval & Decision Workflow"])

def _build_request_response(req: ApprovalRequest) -> ApprovalRequestResponse:
    """Helper to serialize ApprovalRequest with enriched UI context."""
    return ApprovalRequestResponse(
        id=req.id,
        deposit_id=req.deposit_id,
        institution_id=req.institution_id,
        contract_id=req.contract_id,
        request_type=req.request_type,
        status=req.status,
        description=req.description,
        supporting_document_ids=req.supporting_document_ids,
        requested_tenure_months=req.requested_tenure_months,
        extended_maturity_date=req.extended_maturity_date,
        compliance_reference=req.compliance_reference,
        statutory_clause=req.statutory_clause,
        violation_reason=req.violation_reason,
        requested_by_id=req.requested_by_id,
        assigned_officer_id=req.assigned_officer_id,
        decided_by_id=req.decided_by_id,
        submitted_at=req.submitted_at,
        reviewed_at=req.reviewed_at,
        decision_reason=req.decision_reason,
        fdr_number=req.deposit.fdr_number if req.deposit else None,
        deposit_amount=req.deposit.amount if req.deposit else None,
        institution_name=req.institution.name if req.institution else None,
        requested_by_name=req.requested_by.full_name if req.requested_by else None,
        assigned_officer_name=req.assigned_officer.full_name if req.assigned_officer else None,
        decided_by_name=req.decided_by.full_name if req.decided_by else None,
    )

def _check_no_pending_conflicts(db: Session, deposit_id: int):
    """Enforces rule: Prevent duplicate requests of the same or conflicting type when a request is already pending."""
    active_req = db.query(ApprovalRequest).filter(
        ApprovalRequest.deposit_id == deposit_id,
        ApprovalRequest.status.in_([RequestStatus.SUBMITTED, RequestStatus.UNDER_REVIEW])
    ).first()
    if active_req:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An active approval request ({active_req.request_type.value}, Status: {active_req.status.value}) is already pending for this FDR."
        )

@router.post("/renewal", response_model=ApprovalRequestResponse, status_code=status.HTTP_201_CREATED, summary="Submit FDR renewal request")
def submit_renewal_request(
    payload: RenewalRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submits an FDR renewal extension request.
    Institution users can only submit for their college's FDRs.
    Prevents duplicate pending requests and updates deposit status.
    """
    deposit = db.query(Deposit).filter(Deposit.id == payload.deposit_id).first()
    if not deposit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deposit {payload.deposit_id} not found.")

    if current_user.role == UserRole.INSTITUTION:
        if deposit.institution_id != current_user.institution_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot submit renewal for an FDR belonging to another institution."
            )

    _check_no_pending_conflicts(db, deposit.id)

    # Ineligible statuses: already released, rejected, closed
    if deposit.status in [DepositStatus.RELEASED, DepositStatus.CLOSED, DepositStatus.REJECTED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot renew FDR with status '{deposit.status.value}'."
        )

    # Update FDR status
    deposit.status = DepositStatus.RENEWAL_REQUESTED
    deposit.updated_at = utc_now()

    doc_ids_str = ",".join(map(str, payload.supporting_document_ids)) if payload.supporting_document_ids else None

    req = ApprovalRequest(
        deposit_id=deposit.id,
        institution_id=deposit.institution_id,
        contract_id=deposit.contract_id,
        request_type=RequestType.RENEWAL,
        status=RequestStatus.SUBMITTED,
        description=payload.description or f"Renewal extension requested for {payload.requested_tenure_months} months.",
        supporting_document_ids=doc_ids_str,
        requested_tenure_months=payload.requested_tenure_months,
        requested_by_id=current_user.id,
        submitted_at=utc_now()
    )
    db.add(req)
    db.flush()

    # Record Audit Log
    record_audit_log(
        db=db,
        deposit_id=deposit.id,
        action="REQUEST_SUBMITTED_RENEWAL",
        actor_id=current_user.id,
        details=f"Renewal request submitted for {payload.requested_tenure_months} months. Request ID: {req.id}."
    )

    # Broadcast notification to officers
    db.add(Notification(
        recipient_role=UserRole.OFFICER,
        institution_id=deposit.institution_id,
        deposit_id=deposit.id,
        reminder_type="APPROVAL_REQUEST_SUBMITTED",
        title=f"New Renewal Request: FDR {deposit.fdr_number}",
        message=f"Institution has requested {payload.requested_tenure_months} months renewal on FDR {deposit.fdr_number}."
    ))

    db.commit()
    db.refresh(req)
    return _build_request_response(req)

@router.post("/release", response_model=ApprovalRequestResponse, status_code=status.HTTP_201_CREATED, summary="Submit FDR release request")
def submit_release_request(
    payload: ReleaseRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submits an FDR security deposit release request upon course completion or AICTE order.
    Validates institutional tenancy, prevents duplicate requests, and updates deposit status.
    """
    deposit = db.query(Deposit).filter(Deposit.id == payload.deposit_id).first()
    if not deposit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deposit {payload.deposit_id} not found.")

    if current_user.role == UserRole.INSTITUTION:
        if deposit.institution_id != current_user.institution_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot submit release for an FDR belonging to another institution."
            )

    _check_no_pending_conflicts(db, deposit.id)

    if deposit.status in [DepositStatus.RELEASED, DepositStatus.CLOSED, DepositStatus.REJECTED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot release FDR with status '{deposit.status.value}'."
        )

    deposit.status = DepositStatus.RELEASE_REQUESTED
    deposit.updated_at = utc_now()

    doc_ids_str = ",".join(map(str, payload.supporting_document_ids)) if payload.supporting_document_ids else None

    req = ApprovalRequest(
        deposit_id=deposit.id,
        institution_id=deposit.institution_id,
        contract_id=deposit.contract_id,
        request_type=RequestType.RELEASE,
        status=RequestStatus.SUBMITTED,
        description=payload.justification,
        compliance_reference=payload.compliance_reference,
        supporting_document_ids=doc_ids_str,
        requested_by_id=current_user.id,
        submitted_at=utc_now()
    )
    db.add(req)
    db.flush()

    record_audit_log(
        db=db,
        deposit_id=deposit.id,
        action="REQUEST_SUBMITTED_RELEASE",
        actor_id=current_user.id,
        details=f"Release request submitted. Justification: {payload.justification}. Request ID: {req.id}."
    )

    db.add(Notification(
        recipient_role=UserRole.OFFICER,
        institution_id=deposit.institution_id,
        deposit_id=deposit.id,
        reminder_type="APPROVAL_REQUEST_SUBMITTED",
        title=f"New Release Request: FDR {deposit.fdr_number}",
        message=f"Release request submitted for FDR {deposit.fdr_number} (Amount: INR {deposit.amount:,.2f})."
    ))

    db.commit()
    db.refresh(req)
    return _build_request_response(req)

@router.post("/forfeiture", response_model=ApprovalRequestResponse, status_code=status.HTTP_201_CREATED, summary="Submit FDR forfeiture request")
def submit_forfeiture_request(
    payload: ForfeitureRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submits an FDR forfeiture request under breach of statutory handbook clauses.
    """
    deposit = db.query(Deposit).filter(Deposit.id == payload.deposit_id).first()
    if not deposit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deposit {payload.deposit_id} not found.")

    if current_user.role == UserRole.INSTITUTION:
        if deposit.institution_id != current_user.institution_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot submit request for an FDR belonging to another institution."
            )

    _check_no_pending_conflicts(db, deposit.id)

    if deposit.status in [DepositStatus.RELEASED, DepositStatus.CLOSED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot forfeit FDR with status '{deposit.status.value}'."
        )

    deposit.status = DepositStatus.FORFEITURE_REQUESTED
    deposit.updated_at = utc_now()

    doc_ids_str = ",".join(map(str, payload.supporting_document_ids)) if payload.supporting_document_ids else None

    req = ApprovalRequest(
        deposit_id=deposit.id,
        institution_id=deposit.institution_id,
        contract_id=deposit.contract_id,
        request_type=RequestType.FORFEITURE,
        status=RequestStatus.SUBMITTED,
        description=payload.description or f"Forfeiture initiated under {payload.statutory_clause}.",
        statutory_clause=payload.statutory_clause,
        violation_reason=payload.violation_reason,
        supporting_document_ids=doc_ids_str,
        requested_by_id=current_user.id,
        submitted_at=utc_now()
    )
    db.add(req)
    db.flush()

    record_audit_log(
        db=db,
        deposit_id=deposit.id,
        action="REQUEST_SUBMITTED_FORFEITURE",
        actor_id=current_user.id,
        details=f"Forfeiture requested under clause {payload.statutory_clause}. Violation: {payload.violation_reason}."
    )

    db.add(Notification(
        recipient_role=UserRole.OFFICER,
        institution_id=deposit.institution_id,
        deposit_id=deposit.id,
        reminder_type="APPROVAL_REQUEST_SUBMITTED",
        title=f"Forfeiture Initiated: FDR {deposit.fdr_number}",
        message=f"Forfeiture request pending review under clause {payload.statutory_clause}."
    ))

    db.commit()
    db.refresh(req)
    return _build_request_response(req)

@router.get("/my-requests", response_model=List[ApprovalRequestResponse], summary="List approval requests for current user/institution")
def list_my_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists approval requests.
    Institutions only see their college's requests.
    Officers and Admins see all or user-associated requests.
    """
    query = db.query(ApprovalRequest).options(
        joinedload(ApprovalRequest.deposit),
        joinedload(ApprovalRequest.institution),
        joinedload(ApprovalRequest.requested_by),
        joinedload(ApprovalRequest.assigned_officer),
        joinedload(ApprovalRequest.decided_by),
    )

    if current_user.role == UserRole.INSTITUTION:
        query = query.filter(ApprovalRequest.institution_id == current_user.institution_id)

    requests = query.order_by(ApprovalRequest.submitted_at.desc()).all()
    return [_build_request_response(r) for r in requests]

@router.get("/pending", response_model=List[ApprovalRequestResponse], summary="List pending approval requests for officers")
def list_pending_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.OFFICER, UserRole.ADMIN]))
):
    """
    Officer Scrutiny Queue: Returns all requests requiring review (status SUBMITTED or UNDER_REVIEW).
    Strictly restricted to Officers and Admins.
    """
    requests = (
        db.query(ApprovalRequest)
        .options(
            joinedload(ApprovalRequest.deposit),
            joinedload(ApprovalRequest.institution),
            joinedload(ApprovalRequest.requested_by),
            joinedload(ApprovalRequest.assigned_officer),
            joinedload(ApprovalRequest.decided_by),
        )
        .filter(ApprovalRequest.status.in_([RequestStatus.SUBMITTED, RequestStatus.UNDER_REVIEW]))
        .order_by(ApprovalRequest.submitted_at.asc())
        .all()
    )
    return [_build_request_response(r) for r in requests]

@router.get("/{request_id}", response_model=ApprovalRequestResponse, summary="Get approval request details")
def get_approval_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves full details of a specific approval request with tenancy protection."""
    req = (
        db.query(ApprovalRequest)
        .options(
            joinedload(ApprovalRequest.deposit),
            joinedload(ApprovalRequest.institution),
            joinedload(ApprovalRequest.requested_by),
            joinedload(ApprovalRequest.assigned_officer),
            joinedload(ApprovalRequest.decided_by),
        )
        .filter(ApprovalRequest.id == request_id)
        .first()
    )
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Request {request_id} not found.")

    if current_user.role == UserRole.INSTITUTION:
        if req.institution_id != current_user.institution_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot access approval requests belonging to another institution."
            )

    return _build_request_response(req)

@router.patch("/{request_id}/assign", response_model=ApprovalRequestResponse, summary="Assign officer to review request")
def assign_officer(
    request_id: int,
    payload: AssignOfficerRequest = AssignOfficerRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.OFFICER, UserRole.ADMIN]))
):
    """
    Assigns an officer to scrutinize the request and transitions status from SUBMITTED to UNDER_REVIEW.
    """
    req = db.query(ApprovalRequest).filter(ApprovalRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Request {request_id} not found.")

    if req.status not in [RequestStatus.SUBMITTED, RequestStatus.UNDER_REVIEW]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot assign request with status '{req.status.value}'."
        )

    target_officer_id = payload.officer_id or current_user.id
    target_user = db.query(User).filter(User.id == target_officer_id).first()
    if not target_user or target_user.role not in [UserRole.OFFICER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Designated assignee must be a valid Officer or Administrator."
        )

    req.assigned_officer_id = target_officer_id
    req.status = RequestStatus.UNDER_REVIEW
    req.reviewed_at = utc_now()

    record_audit_log(
        db=db,
        deposit_id=req.deposit_id,
        action="REQUEST_ASSIGNED",
        actor_id=current_user.id,
        details=f"Request {req.id} ({req.request_type.value}) assigned to {target_user.full_name} for scrutiny."
    )

    db.commit()
    db.refresh(req)
    return _build_request_response(req)

@router.patch("/{request_id}/approve", response_model=ApprovalRequestResponse, summary="Officer approves request")
def approve_request(
    request_id: int,
    payload: ApprovalDecisionRequest = ApprovalDecisionRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.OFFICER, UserRole.ADMIN]))
):
    """
    Officer or Admin decision to approve renewal, release, or forfeiture.
    Institutions cannot approve their own requests.
    Updates FDR status and records complete audit trail and institution notifications.
    """
    req = db.query(ApprovalRequest).filter(ApprovalRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Request {request_id} not found.")

    if req.status not in [RequestStatus.SUBMITTED, RequestStatus.UNDER_REVIEW]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve request with status '{req.status.value}'. Must be in SUBMITTED or UNDER_REVIEW state."
        )

    deposit = db.query(Deposit).filter(Deposit.id == req.deposit_id).first()
    if not deposit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deposit {req.deposit_id} not found.")

    today = date.today()

    if req.request_type == RequestType.RENEWAL:
        # Calculate new maturity date
        if payload.extended_maturity_date:
            new_maturity = payload.extended_maturity_date
        else:
            months = req.requested_tenure_months or 12
            new_maturity = today + timedelta(days=30 * months)

        if new_maturity <= deposit.issue_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New extended maturity date must be after original issue date."
            )

        deposit.status = DepositStatus.ACTIVE
        deposit.maturity_date = new_maturity
        deposit.verified_by_id = current_user.id
        deposit.verified_at = utc_now()
        req.extended_maturity_date = new_maturity

    elif req.request_type == RequestType.RELEASE:
        deposit.status = DepositStatus.RELEASED
        deposit.verified_by_id = current_user.id
        deposit.verified_at = utc_now()

    elif req.request_type == RequestType.FORFEITURE:
        deposit.status = DepositStatus.CLOSED
        deposit.verified_by_id = current_user.id
        deposit.verified_at = utc_now()

    req.status = RequestStatus.APPROVED
    req.decided_by_id = current_user.id
    req.reviewed_at = utc_now()
    req.decision_reason = payload.decision_remarks or f"Approved by {current_user.full_name}."

    record_audit_log(
        db=db,
        deposit_id=deposit.id,
        action=f"REQUEST_APPROVED_{req.request_type.value}",
        actor_id=current_user.id,
        details=f"Request {req.id} approved by Officer {current_user.full_name}. Decision remarks: {req.decision_reason}."
    )

    # Notify institution
    inst_users = db.query(User).filter(
        User.institution_id == req.institution_id,
        User.role == UserRole.INSTITUTION
    ).all()
    for u in inst_users:
        db.add(Notification(
            recipient_user_id=u.id,
            institution_id=req.institution_id,
            deposit_id=deposit.id,
            reminder_type=f"DECISION_{req.request_type.value}_APPROVED",
            title=f"Request Approved: {req.request_type.value} on FDR {deposit.fdr_number}",
            message=f"Your {req.request_type.value} request for FDR {deposit.fdr_number} has been approved by AICTE. Remarks: {req.decision_reason}."
        ))

    db.commit()
    db.refresh(req)
    return _build_request_response(req)

@router.patch("/{request_id}/reject", response_model=ApprovalRequestResponse, summary="Officer rejects request")
def reject_request(
    request_id: int,
    payload: RejectionDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.OFFICER, UserRole.ADMIN]))
):
    """
    Officer or Admin decision to reject request.
    Mandatory non-empty rejection reason is required.
    Reverts FDR status and notifies the submitting institution.
    """
    req = db.query(ApprovalRequest).filter(ApprovalRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Request {request_id} not found.")

    if req.status not in [RequestStatus.SUBMITTED, RequestStatus.UNDER_REVIEW]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject request with status '{req.status.value}'. Must be in SUBMITTED or UNDER_REVIEW state."
        )

    deposit = db.query(Deposit).filter(Deposit.id == req.deposit_id).first()
    if not deposit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deposit {req.deposit_id} not found.")

    # Revert FDR status to active or action required depending on maturity date
    today = date.today()
    if deposit.maturity_date < today:
        deposit.status = DepositStatus.MATURED_ACTION_REQUIRED
    else:
        deposit.status = DepositStatus.ACTIVE

    deposit.verified_by_id = current_user.id
    deposit.verification_remarks = f"Request {req.request_type.value} rejected: {payload.rejection_reason}"
    deposit.updated_at = utc_now()

    req.status = RequestStatus.REJECTED
    req.decided_by_id = current_user.id
    req.reviewed_at = utc_now()
    req.decision_reason = payload.rejection_reason.strip()

    record_audit_log(
        db=db,
        deposit_id=deposit.id,
        action=f"REQUEST_REJECTED_{req.request_type.value}",
        actor_id=current_user.id,
        details=f"Request {req.id} rejected by Officer {current_user.full_name}. Reason: {req.decision_reason}."
    )

    inst_users = db.query(User).filter(
        User.institution_id == req.institution_id,
        User.role == UserRole.INSTITUTION
    ).all()
    for u in inst_users:
        db.add(Notification(
            recipient_user_id=u.id,
            institution_id=req.institution_id,
            deposit_id=deposit.id,
            reminder_type=f"DECISION_{req.request_type.value}_REJECTED",
            title=f"Request Rejected: {req.request_type.value} on FDR {deposit.fdr_number}",
            message=f"Your {req.request_type.value} request for FDR {deposit.fdr_number} was rejected by AICTE. Reason: {req.decision_reason}."
        ))

    db.commit()
    db.refresh(req)
    return _build_request_response(req)

@router.patch("/{request_id}/cancel", response_model=ApprovalRequestResponse, summary="Institution cancels pending request")
def cancel_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submitting institution cancels an eligible pending request (SUBMITTED or UNDER_REVIEW).
    Reverts FDR status and records cancellation event.
    """
    req = db.query(ApprovalRequest).filter(ApprovalRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Request {request_id} not found.")

    if current_user.role == UserRole.INSTITUTION:
        if req.institution_id != current_user.institution_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot cancel requests belonging to another institution."
            )

    if req.status not in [RequestStatus.SUBMITTED, RequestStatus.UNDER_REVIEW]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel request with status '{req.status.value}'. Only SUBMITTED or UNDER_REVIEW requests can be cancelled."
        )

    deposit = db.query(Deposit).filter(Deposit.id == req.deposit_id).first()
    if deposit:
        today = date.today()
        if deposit.maturity_date < today:
            deposit.status = DepositStatus.MATURED_ACTION_REQUIRED
        else:
            deposit.status = DepositStatus.ACTIVE
        deposit.updated_at = utc_now()

    req.status = RequestStatus.CANCELLED
    req.reviewed_at = utc_now()
    req.decision_reason = "Cancelled by submitting institution."

    record_audit_log(
        db=db,
        deposit_id=req.deposit_id,
        action="REQUEST_CANCELLED",
        actor_id=current_user.id,
        details=f"Request {req.id} ({req.request_type.value}) cancelled by user {current_user.full_name}."
    )

    db.commit()
    db.refresh(req)
    return _build_request_response(req)
