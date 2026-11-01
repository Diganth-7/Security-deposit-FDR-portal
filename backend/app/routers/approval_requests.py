"""
Approval workflow for FDR renewal, release and forfeiture (extends the Phase 2 requests).

State machine (details in docs/APPROVAL_WORKFLOW.md):
    SUBMITTED   -> UNDER_REVIEW   (assign / review started)
    SUBMITTED   -> APPROVED | REJECTED | CANCELLED
    UNDER_REVIEW -> APPROVED | REJECTED | CANCELLED
APPROVED, REJECTED and CANCELLED are final. DRAFT exists in the enum for future use
but no endpoint creates drafts.
"""
import logging
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from backend.app.auth.dependencies import get_current_user, require_role
from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models.approval_request import ApprovalRequest, RequestStatus, RequestType
from backend.app.models.contract import Contract, ContractStatus
from backend.app.models.deposit import Deposit, DepositStatus
from backend.app.models.document import Document, DocumentVerificationStatus
from backend.app.models.notification import Notification
from backend.app.models.user import User, UserRole
from backend.app.schemas.approval_request import (
    ApprovalDecisionRequest,
    ApprovalRequestResponse,
    AssignOfficerRequest,
    ForfeitureRequestCreate,
    ReleaseRequestCreate,
    RejectionDecisionRequest,
    RenewalRequestCreate,
)
from backend.app.services.audit_service import record_audit_log
from backend.app.utils.clock import add_months, today, utc_now

logger = logging.getLogger("aicte_fdr.approval_requests")

router = APIRouter(prefix="/requests", tags=["Approval & Decision Workflow"])

OPEN_STATES = [RequestStatus.SUBMITTED, RequestStatus.UNDER_REVIEW]
# FDR states from which no new request may be raised.
INELIGIBLE_DEPOSIT_STATES = [
    DepositStatus.PENDING_VERIFICATION, DepositStatus.REJECTED,
    DepositStatus.RELEASED, DepositStatus.CLOSED,
]
REQUESTED_STATES = [
    DepositStatus.RENEWAL_REQUESTED, DepositStatus.RELEASE_REQUESTED, DepositStatus.FORFEITURE_REQUESTED,
]
PENDING_DEPOSIT_STATUS = {
    RequestType.RENEWAL: DepositStatus.RENEWAL_REQUESTED,
    RequestType.RELEASE: DepositStatus.RELEASE_REQUESTED,
    RequestType.FORFEITURE: DepositStatus.FORFEITURE_REQUESTED,
}


# --------------------------------------------------------------------------- #
# Permissions (configurable through APPROVAL_SUBMIT_ROLES_* / APPROVAL_DECIDE_ROLES_*)
# --------------------------------------------------------------------------- #
def _allowed_roles(action: str, req_type: RequestType) -> set:
    return settings.parse_roles(getattr(settings, f"APPROVAL_{action}_ROLES_{req_type.value}"))


def _require_permission(user: User, action: str, req_type: RequestType) -> None:
    if user.role.value not in _allowed_roles(action, req_type):
        verb = "submit" if action == "SUBMIT" else "decide"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Your role ({user.role.value}) may not {verb} {req_type.value} requests.",
        )


def _require_tenancy(user: User, institution_id: int, what: str) -> None:
    if user.role == UserRole.INSTITUTION and institution_id != user.institution_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: cannot {what} belonging to another institution.",
        )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _query_with_context(db: Session):
    return db.query(ApprovalRequest).options(
        joinedload(ApprovalRequest.deposit),
        joinedload(ApprovalRequest.institution),
        joinedload(ApprovalRequest.requested_by),
        joinedload(ApprovalRequest.assigned_officer),
        joinedload(ApprovalRequest.decided_by),
    )


def _build_request_response(req: ApprovalRequest) -> ApprovalRequestResponse:
    """Serialises an ApprovalRequest with the context the UI needs."""
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


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _set_deposit_status(db: Session, deposit: Deposit, new_status: DepositStatus, actor: User, reason: str) -> None:
    """Changes the FDR status and writes an FDR_STATUS_CHANGED audit entry (same transaction)."""
    old = deposit.status
    if old == new_status:
        return
    deposit.status = new_status
    deposit.updated_at = utc_now()
    record_audit_log(
        db, deposit_id=deposit.id, action="FDR_STATUS_CHANGED", actor_id=actor.id,
        details=f"FDR {deposit.fdr_number}: {old.value} -> {new_status.value}. {reason}",
        before={"status": old}, after={"status": new_status}, commit=False,
    )


def _restore_deposit_status(req: ApprovalRequest, deposit: Deposit) -> DepositStatus:
    """The status the FDR had before this request; never a *_REQUESTED state."""
    try:
        prev = DepositStatus(req.previous_deposit_status) if req.previous_deposit_status else None
    except ValueError:
        prev = None
    if prev is None or prev in REQUESTED_STATES or prev in INELIGIBLE_DEPOSIT_STATES:
        prev = DepositStatus.ACTIVE
    if prev in (DepositStatus.ACTIVE, DepositStatus.VERIFIED, DepositStatus.MATURITY_APPROACHING) \
            and deposit.maturity_date < today():
        return DepositStatus.MATURED_ACTION_REQUIRED
    return prev


def _validate_supporting_documents(db: Session, deposit: Deposit, ids: Optional[List[int]]) -> Optional[str]:
    if not ids:
        return None
    unique_ids = sorted(set(ids))
    found = db.query(Document.id).filter(Document.id.in_(unique_ids), Document.deposit_id == deposit.id).all()
    if len(found) != len(unique_ids):
        raise _bad_request("One or more supporting documents do not exist for this FDR.")
    return ",".join(str(i) for i in unique_ids)


def _check_contract_rules(deposit: Deposit, req_type: RequestType) -> None:
    """Release and forfeiture must follow the terms of the linked contract."""
    contract: Optional[Contract] = deposit.contract
    if req_type == RequestType.RELEASE and contract is not None and contract.status == ContractStatus.ACTIVE:
        raise _bad_request(
            f"Contract {contract.contract_number} is still ACTIVE: the security deposit cannot be released "
            "until the contract is COMPLETED, EXPIRED or TERMINATED."
        )
    if req_type == RequestType.FORFEITURE and settings.FORFEITURE_REQUIRES_CONTRACT:
        if contract is None:
            raise _bad_request("Forfeiture must be based on contract terms: link this FDR to a contract first.")
        if contract.status not in (ContractStatus.ACTIVE, ContractStatus.EXPIRED, ContractStatus.TERMINATED):
            raise _bad_request(
                f"Forfeiture is not available for a contract with status {contract.status.value}."
            )


def _notify_institution_users(db: Session, req: ApprovalRequest, deposit: Deposit, kind: str, title: str, message: str) -> None:
    users = db.query(User).filter(
        User.institution_id == req.institution_id, User.role == UserRole.INSTITUTION, User.is_active.is_(True)
    ).all()
    for u in users:
        db.add(Notification(
            recipient_user_id=u.id, institution_id=req.institution_id, deposit_id=deposit.id,
            reminder_type=kind, title=title, message=message,
        ))


def _submit(db: Session, user: User, req_type: RequestType, payload, fields: dict, description: str, audit_text: str) -> ApprovalRequest:
    """Shared submission path for the three request types."""
    _require_permission(user, "SUBMIT", req_type)
    deposit = db.query(Deposit).filter(Deposit.id == payload.deposit_id).with_for_update().first()
    if not deposit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deposit {payload.deposit_id} not found.")
    _require_tenancy(user, deposit.institution_id, f"submit a {req_type.value.lower()} request for an FDR")

    active = db.query(ApprovalRequest).filter(
        ApprovalRequest.deposit_id == deposit.id, ApprovalRequest.status.in_(OPEN_STATES)
    ).first()
    if active:
        raise _bad_request(
            f"An active approval request ({active.request_type.value}, Status: {active.status.value}) "
            "is already pending for this FDR."
        )
    if deposit.status in INELIGIBLE_DEPOSIT_STATES:
        raise _bad_request(f"Cannot raise a {req_type.value.lower()} request for an FDR with status '{deposit.status.value}'.")
    _check_contract_rules(deposit, req_type)
    doc_ids = _validate_supporting_documents(db, deposit, payload.supporting_document_ids)

    req = ApprovalRequest(
        deposit_id=deposit.id, institution_id=deposit.institution_id, contract_id=deposit.contract_id,
        request_type=req_type, status=RequestStatus.SUBMITTED, description=description,
        supporting_document_ids=doc_ids, previous_deposit_status=deposit.status.value,
        requested_by_id=user.id, submitted_at=utc_now(), **fields,
    )
    db.add(req)
    db.flush()

    record_audit_log(
        db, deposit_id=deposit.id, action=f"REQUEST_SUBMITTED_{req_type.value}", actor_id=user.id,
        details=f"{audit_text} Request ID: {req.id}.", entity_type="APPROVAL_REQUEST", entity_id=req.id,
        after={"status": RequestStatus.SUBMITTED, "type": req_type}, commit=False,
    )
    _set_deposit_status(db, deposit, PENDING_DEPOSIT_STATUS[req_type], user, f"Request {req.id} submitted.")

    db.add(Notification(
        recipient_role=UserRole.OFFICER, institution_id=deposit.institution_id, deposit_id=deposit.id,
        reminder_type="APPROVAL_REQUEST_SUBMITTED",
        title=f"New {req_type.value.title()} Request: FDR {deposit.fdr_number}",
        message=f"{req_type.value.title()} request submitted for FDR {deposit.fdr_number} "
                f"(INR {deposit.amount:,.2f}) by {user.full_name}.",
    ))
    if user.role != UserRole.INSTITUTION:  # authority-initiated (e.g. forfeiture): tell the institution
        _notify_institution_users(
            db, req, deposit, "APPROVAL_REQUEST_SUBMITTED",
            f"{req_type.value.title()} initiated on FDR {deposit.fdr_number}",
            f"AICTE has initiated a {req_type.value.lower()} request for FDR {deposit.fdr_number}.",
        )
    db.commit()
    db.refresh(req)
    return req


def _load_open_request_for_decision(db: Session, request_id: int, user: User, action: str) -> ApprovalRequest:
    req = db.query(ApprovalRequest).filter(ApprovalRequest.id == request_id).with_for_update().first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Request {request_id} not found.")
    _require_permission(user, "DECIDE", req.request_type)
    if req.requested_by_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot decide a request you submitted yourself.",
        )
    if req.status not in OPEN_STATES:
        raise _bad_request(
            f"Cannot {action} request with status '{req.status.value}'. Must be in SUBMITTED or UNDER_REVIEW state."
        )
    if req.assigned_officer_id and req.assigned_officer_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This request is assigned to another officer. Only the assignee or an administrator may decide it.",
        )
    return req


# --------------------------------------------------------------------------- #
# Submission
# --------------------------------------------------------------------------- #
@router.post("/renewal", response_model=ApprovalRequestResponse, status_code=status.HTTP_201_CREATED, summary="Submit FDR renewal request")
def submit_renewal_request(payload: RenewalRequestCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Requests extension of an FDR. Institutions can only act for their own FDRs."""
    req = _submit(
        db, current_user, RequestType.RENEWAL, payload,
        fields={"requested_tenure_months": payload.requested_tenure_months},
        description=payload.description or f"Renewal extension requested for {payload.requested_tenure_months} months.",
        audit_text=f"Renewal request submitted for {payload.requested_tenure_months} months.",
    )
    return _build_request_response(req)


@router.post("/release", response_model=ApprovalRequestResponse, status_code=status.HTTP_201_CREATED, summary="Submit FDR release request")
def submit_release_request(payload: ReleaseRequestCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Requests return of the security deposit. Blocked while the linked contract is ACTIVE.
    Reaching maturity does not by itself authorise release."""
    req = _submit(
        db, current_user, RequestType.RELEASE, payload,
        fields={"compliance_reference": payload.compliance_reference},
        description=payload.justification,
        audit_text=f"Release request submitted. Justification: {payload.justification}.",
    )
    return _build_request_response(req)


@router.post("/forfeiture", response_model=ApprovalRequestResponse, status_code=status.HTTP_201_CREATED, summary="Submit FDR forfeiture request")
def submit_forfeiture_request(payload: ForfeitureRequestCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Initiates forfeiture under a stated clause. Needs a linked contract (configurable)."""
    req = _submit(
        db, current_user, RequestType.FORFEITURE, payload,
        fields={"statutory_clause": payload.statutory_clause, "violation_reason": payload.violation_reason},
        description=payload.description or f"Forfeiture initiated under {payload.statutory_clause}.",
        audit_text=f"Forfeiture requested under clause {payload.statutory_clause}. Violation: {payload.violation_reason}.",
    )
    return _build_request_response(req)


# --------------------------------------------------------------------------- #
# Listing
# --------------------------------------------------------------------------- #
@router.get("/my-requests", response_model=List[ApprovalRequestResponse], summary="List approval requests visible to the current user")
def list_my_requests(
    status_filter: Optional[RequestStatus] = Query(None, alias="status"),
    request_type: Optional[RequestType] = Query(None),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Institutions see their own college's requests; officers and admins see all."""
    query = _query_with_context(db)
    if current_user.role == UserRole.INSTITUTION:
        query = query.filter(ApprovalRequest.institution_id == current_user.institution_id)
    if status_filter:
        query = query.filter(ApprovalRequest.status == status_filter)
    if request_type:
        query = query.filter(ApprovalRequest.request_type == request_type)
    return [_build_request_response(r) for r in query.order_by(ApprovalRequest.submitted_at.desc()).limit(limit).all()]


@router.get("/pending", response_model=List[ApprovalRequestResponse], summary="Officer queue of requests awaiting a decision")
def list_pending_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.OFFICER, UserRole.ADMIN])),
):
    """Requests in SUBMITTED or UNDER_REVIEW. Officers and admins only."""
    rows = (
        _query_with_context(db).filter(ApprovalRequest.status.in_(OPEN_STATES))
        .order_by(ApprovalRequest.submitted_at.asc()).all()
    )
    return [_build_request_response(r) for r in rows]


@router.get("/{request_id}", response_model=ApprovalRequestResponse, summary="Get approval request details")
def get_approval_request(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    req = _query_with_context(db).filter(ApprovalRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Request {request_id} not found.")
    _require_tenancy(current_user, req.institution_id, "access approval requests")
    return _build_request_response(req)


# --------------------------------------------------------------------------- #
# Review and decisions
# --------------------------------------------------------------------------- #
@router.patch("/{request_id}/assign", response_model=ApprovalRequestResponse, summary="Assign an officer and start review")
def assign_officer(
    request_id: int,
    payload: AssignOfficerRequest = AssignOfficerRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.OFFICER, UserRole.ADMIN])),
):
    """SUBMITTED -> UNDER_REVIEW. Only roles allowed to decide this request type may take it for review."""
    req = db.query(ApprovalRequest).filter(ApprovalRequest.id == request_id).with_for_update().first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Request {request_id} not found.")
    _require_permission(current_user, "DECIDE", req.request_type)
    if req.status not in OPEN_STATES:
        raise _bad_request(f"Cannot assign request with status '{req.status.value}'.")

    target_id = payload.officer_id or current_user.id
    target = db.query(User).filter(User.id == target_id, User.is_active.is_(True)).first()
    if not target or target.role.value not in _allowed_roles("DECIDE", req.request_type):
        raise _bad_request("Designated assignee must be an active user allowed to decide this request type.")
    if target.id == req.requested_by_id:
        raise _bad_request("The requester cannot be assigned to review their own request.")

    started = req.status == RequestStatus.SUBMITTED
    req.assigned_officer_id = target.id
    req.status = RequestStatus.UNDER_REVIEW
    req.reviewed_at = utc_now()
    record_audit_log(
        db, deposit_id=req.deposit_id, action="REQUEST_ASSIGNED", actor_id=current_user.id,
        details=f"Request {req.id} ({req.request_type.value}) assigned to {target.full_name} for scrutiny.",
        entity_type="APPROVAL_REQUEST", entity_id=req.id, commit=False,
    )
    if started:
        record_audit_log(
            db, deposit_id=req.deposit_id, action="REQUEST_REVIEW_STARTED", actor_id=current_user.id,
            details=f"Review of request {req.id} started.", entity_type="APPROVAL_REQUEST", entity_id=req.id,
            before={"status": RequestStatus.SUBMITTED}, after={"status": RequestStatus.UNDER_REVIEW}, commit=False,
        )
    db.commit()
    db.refresh(req)
    return _build_request_response(req)


@router.patch("/{request_id}/approve", response_model=ApprovalRequestResponse, summary="Approve a request")
def approve_request(
    request_id: int,
    payload: ApprovalDecisionRequest = ApprovalDecisionRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.OFFICER, UserRole.ADMIN])),
):
    """
    Approves a renewal, release or forfeiture.

    Needs: a role allowed to decide this type, someone other than the requester,
    written decision remarks, and (release/forfeiture, when configured) at least one
    VERIFIED supporting document on the FDR. Release and forfeiture are re-checked
    against the linked contract at decision time.
    """
    req = _load_open_request_for_decision(db, request_id, current_user, "approve")
    deposit = db.query(Deposit).filter(Deposit.id == req.deposit_id).with_for_update().first()
    if not deposit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deposit {req.deposit_id} not found.")

    remarks = (payload.decision_remarks or "").strip()
    if len(remarks) < 3:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Approval needs written decision remarks recording the basis for the decision.")

    if req.request_type in (RequestType.RELEASE, RequestType.FORFEITURE):
        _check_contract_rules(deposit, req.request_type)
        if settings.APPROVAL_REQUIRE_VERIFIED_DOCUMENT:
            verified = db.query(Document.id).filter(
                Document.deposit_id == deposit.id,
                Document.verification_status == DocumentVerificationStatus.VERIFIED,
            ).first()
            if not verified:
                raise _bad_request("Approval needs supporting information: at least one VERIFIED document on this FDR.")

    before = {"maturity_date": deposit.maturity_date, "status": deposit.status}
    if req.request_type == RequestType.RENEWAL:
        if payload.extended_maturity_date:
            new_maturity = payload.extended_maturity_date
        else:
            base = max(deposit.maturity_date, today())
            new_maturity = add_months(base, req.requested_tenure_months or 12)
        if new_maturity <= deposit.maturity_date:
            raise _bad_request("The new maturity date must be later than the current maturity date.")
        deposit.maturity_date = new_maturity
        req.extended_maturity_date = new_maturity
        new_status, outcome = DepositStatus.ACTIVE, f"Maturity extended to {new_maturity}."
    elif req.request_type == RequestType.RELEASE:
        new_status, outcome = DepositStatus.RELEASED, "Security deposit released."
    else:
        # The FDR enum has no FORFEITED state; CLOSED plus the approved FORFEITURE request records it.
        new_status, outcome = DepositStatus.CLOSED, "FDR forfeited and closed."

    deposit.verified_by_id = current_user.id
    deposit.verified_at = utc_now()
    _set_deposit_status(db, deposit, new_status, current_user, f"Request {req.id} approved. {outcome}")

    req.status = RequestStatus.APPROVED
    req.decided_by_id = current_user.id
    req.reviewed_at = utc_now()
    req.decision_reason = remarks
    record_audit_log(
        db, deposit_id=deposit.id, action=f"REQUEST_APPROVED_{req.request_type.value}", actor_id=current_user.id,
        details=f"Request {req.id} approved by Officer {current_user.full_name}. Decision remarks: {remarks}.",
        entity_type="APPROVAL_REQUEST", entity_id=req.id,
        before={**before, "request_status": RequestStatus.UNDER_REVIEW if req.assigned_officer_id else RequestStatus.SUBMITTED},
        after={"maturity_date": deposit.maturity_date, "status": deposit.status, "request_status": RequestStatus.APPROVED},
        commit=False,
    )
    _notify_institution_users(
        db, req, deposit, f"DECISION_{req.request_type.value}_APPROVED",
        f"Request Approved: {req.request_type.value} on FDR {deposit.fdr_number}",
        f"Your {req.request_type.value} request for FDR {deposit.fdr_number} has been approved by AICTE. Remarks: {remarks}.",
    )
    db.commit()
    db.refresh(req)
    return _build_request_response(req)


@router.patch("/{request_id}/reject", response_model=ApprovalRequestResponse, summary="Reject a request")
def reject_request(
    request_id: int,
    payload: RejectionDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role([UserRole.OFFICER, UserRole.ADMIN])),
):
    """Rejects a request. A written reason is mandatory; the FDR returns to its previous status."""
    req = _load_open_request_for_decision(db, request_id, current_user, "reject")
    deposit = db.query(Deposit).filter(Deposit.id == req.deposit_id).with_for_update().first()
    if not deposit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deposit {req.deposit_id} not found.")
    reason = payload.rejection_reason.strip()
    if len(reason) < 3:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A rejection reason is required.")

    deposit.verification_remarks = f"Request {req.request_type.value} rejected: {reason}"
    _set_deposit_status(db, deposit, _restore_deposit_status(req, deposit), current_user, f"Request {req.id} rejected.")

    prior = req.status
    req.status = RequestStatus.REJECTED
    req.decided_by_id = current_user.id
    req.reviewed_at = utc_now()
    req.decision_reason = reason
    record_audit_log(
        db, deposit_id=deposit.id, action=f"REQUEST_REJECTED_{req.request_type.value}", actor_id=current_user.id,
        details=f"Request {req.id} rejected by Officer {current_user.full_name}. Reason: {reason}.",
        entity_type="APPROVAL_REQUEST", entity_id=req.id,
        before={"request_status": prior}, after={"request_status": RequestStatus.REJECTED}, commit=False,
    )
    _notify_institution_users(
        db, req, deposit, f"DECISION_{req.request_type.value}_REJECTED",
        f"Request Rejected: {req.request_type.value} on FDR {deposit.fdr_number}",
        f"Your {req.request_type.value} request for FDR {deposit.fdr_number} was rejected by AICTE. Reason: {reason}.",
    )
    db.commit()
    db.refresh(req)
    return _build_request_response(req)


@router.patch("/{request_id}/cancel", response_model=ApprovalRequestResponse, summary="Cancel a pending request")
def cancel_request(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """The submitting institution (or the officer/admin who raised it) withdraws a pending request."""
    req = db.query(ApprovalRequest).filter(ApprovalRequest.id == request_id).with_for_update().first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Request {request_id} not found.")
    _require_tenancy(current_user, req.institution_id, "cancel requests")
    if current_user.role != UserRole.ADMIN and req.requested_by_id != current_user.id \
            and not (current_user.role == UserRole.INSTITUTION and current_user.institution_id == req.institution_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the requester, their institution or an administrator may cancel this request.")
    if req.status not in OPEN_STATES:
        raise _bad_request(
            f"Cannot cancel request with status '{req.status.value}'. Only SUBMITTED or UNDER_REVIEW requests can be cancelled."
        )

    deposit = db.query(Deposit).filter(Deposit.id == req.deposit_id).with_for_update().first()
    if deposit:
        _set_deposit_status(db, deposit, _restore_deposit_status(req, deposit), current_user, f"Request {req.id} cancelled.")

    prior = req.status
    req.status = RequestStatus.CANCELLED
    req.reviewed_at = utc_now()
    req.decision_reason = f"Cancelled by {current_user.full_name}."
    record_audit_log(
        db, deposit_id=req.deposit_id, action="REQUEST_CANCELLED", actor_id=current_user.id,
        details=f"Request {req.id} ({req.request_type.value}) cancelled by user {current_user.full_name}.",
        entity_type="APPROVAL_REQUEST", entity_id=req.id,
        before={"request_status": prior}, after={"request_status": RequestStatus.CANCELLED}, commit=False,
    )
    if deposit:
        db.add(Notification(
            recipient_role=UserRole.OFFICER, institution_id=req.institution_id, deposit_id=deposit.id,
            reminder_type="APPROVAL_REQUEST_CANCELLED",
            title=f"Request Cancelled: FDR {deposit.fdr_number}",
            message=f"{req.request_type.value.title()} request {req.id} for FDR {deposit.fdr_number} was cancelled.",
        ))
    db.commit()
    db.refresh(req)
    return _build_request_response(req)
