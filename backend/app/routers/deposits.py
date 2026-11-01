from datetime import datetime, date, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from backend.app.database import get_db
from backend.app.models.deposit import Deposit, DepositStatus
from backend.app.models.institution import Institution
from backend.app.models.user import User, UserRole
from backend.app.models.notification import Notification
from backend.app.models.document import Document
from backend.app.schemas.document import DocumentResponse
from backend.app.schemas.deposit import (
    DepositCreate,
    DepositResponse,
    DepositStatusUpdate,
    DepositRenewalRequest,
    DepositReleaseRequest,
    DepositForfeitureRequest,
    DepositActionDecision,
    DepositMaturityItem,
)
from backend.app.auth.dependencies import (
    get_current_user,
    require_officer_or_admin,
    require_role,
)
from backend.app.routers import approval_requests as wf
from backend.app.utils.clock import today as app_today
from backend.app.services.audit_service import record_audit_log
from backend.app.utils.clock import utc_now

router = APIRouter(prefix="/deposits", tags=["Deposits & FDRs"])

@router.get("", response_model=List[DepositResponse])
def list_deposits(
    status_filter: Optional[DepositStatus] = Query(None, alias="status", description="Filter by FDR Status"),
    bank: Optional[str] = Query(None, description="Filter by bank name"),
    institution_id: Optional[int] = Query(None, description="Filter by institution ID (Admin/Officer only)"),
    search: Optional[str] = Query(None, description="Search by FDR number or bank"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists Fixed Deposit Receipts (FDRs).
    - If user is an INSTITUTION: Only shows deposits belonging to their institution.
    - If user is an OFFICER or ADMIN: Shows all deposits across India, with optional filters.
    """
    query = db.query(Deposit).options(
        joinedload(Deposit.institution),
        joinedload(Deposit.submitted_by),
        joinedload(Deposit.verified_by)
    )

    # Role-based scoping: Institution can only see their own FDRs
    if current_user.role == UserRole.INSTITUTION:
        if not current_user.institution_id:
            return []
        query = query.filter(Deposit.institution_id == current_user.institution_id)
    elif institution_id:
        query = query.filter(Deposit.institution_id == institution_id)

    if status_filter:
        query = query.filter(Deposit.status == status_filter)

    if bank:
        query = query.filter(Deposit.bank_name.ilike(f"%{bank}%"))

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Deposit.fdr_number.ilike(search_pattern)) |
            (Deposit.bank_name.ilike(search_pattern))
        )

    return query.order_by(Deposit.created_at.desc()).all()

@router.get("/upcoming-maturities", response_model=List[DepositMaturityItem])
def get_upcoming_maturities(
    days: int = Query(30, ge=1, le=365, description="Filter FDRs maturing within N days (default: 30)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists FDRs approaching maturity within the specified number of days.
    Respects role-based institution access.
    """
    today = app_today()
    cutoff_date = today + timedelta(days=days)

    query = db.query(Deposit).options(joinedload(Deposit.institution)).filter(
        Deposit.maturity_date >= today,
        Deposit.maturity_date <= cutoff_date,
        Deposit.status.in_([
            DepositStatus.ACTIVE,
            DepositStatus.MATURITY_APPROACHING,
            DepositStatus.VERIFIED
        ])
    )

    if current_user.role == UserRole.INSTITUTION:
        if not current_user.institution_id:
            return []
        query = query.filter(Deposit.institution_id == current_user.institution_id)

    results = query.order_by(Deposit.maturity_date.asc()).all()

    items = []
    for d in results:
        days_rem = (d.maturity_date - today).days
        items.append(DepositMaturityItem(
            id=d.id,
            fdr_number=d.fdr_number,
            amount=d.amount,
            bank_name=d.bank_name,
            issue_date=d.issue_date,
            maturity_date=d.maturity_date,
            status=d.status,
            contract_reference=d.contract_reference,
            institution_id=d.institution_id,
            institution_name=d.institution.name if d.institution else None,
            days_remaining=days_rem,
            maturity_status=f"Maturing in {days_rem} days"
        ))

    return items

@router.get("/matured", response_model=List[DepositMaturityItem])
def get_matured_deposits(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists FDRs that have already reached their maturity date or are in action-required / request states.
    Respects role-based institution access.
    """
    today = app_today()
    matured_statuses = [
        DepositStatus.MATURED_ACTION_REQUIRED,
        DepositStatus.MATURED,
        DepositStatus.RENEWAL_REQUESTED,
        DepositStatus.RELEASE_REQUESTED,
        DepositStatus.FORFEITURE_REQUESTED,
        DepositStatus.CLOSED
    ]

    query = db.query(Deposit).options(joinedload(Deposit.institution)).filter(
        (Deposit.maturity_date <= today) | (Deposit.status.in_(matured_statuses))
    )

    if current_user.role == UserRole.INSTITUTION:
        if not current_user.institution_id:
            return []
        query = query.filter(Deposit.institution_id == current_user.institution_id)

    results = query.order_by(Deposit.maturity_date.asc()).all()

    items = []
    for d in results:
        days_rem = (d.maturity_date - today).days
        items.append(DepositMaturityItem(
            id=d.id,
            fdr_number=d.fdr_number,
            amount=d.amount,
            bank_name=d.bank_name,
            issue_date=d.issue_date,
            maturity_date=d.maturity_date,
            status=d.status,
            contract_reference=d.contract_reference,
            institution_id=d.institution_id,
            institution_name=d.institution.name if d.institution else None,
            days_remaining=days_rem,
            maturity_status="Matured" if days_rem <= 0 else f"{days_rem} days remaining"
        ))

    return items

@router.post("", response_model=DepositResponse, status_code=status.HTTP_201_CREATED)
def submit_deposit(
    deposit_in: DepositCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submits a new FDR / Security Deposit for verification.
    """
    if current_user.role == UserRole.OFFICER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verification Officers cannot submit deposits. Their role is restricted to review and verification."
        )

    target_institution_id = deposit_in.institution_id
    if current_user.role == UserRole.INSTITUTION:
        if not current_user.institution_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your user account is not associated with an AICTE approved institution."
            )
        target_institution_id = current_user.institution_id
    elif not target_institution_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Institution ID is required when submitting as an Administrator."
        )

    inst = db.query(Institution).filter(Institution.id == target_institution_id).first()
    if not inst:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Institution with ID {target_institution_id} does not exist."
        )

    existing_fdr = db.query(Deposit).filter(Deposit.fdr_number == deposit_in.fdr_number.strip()).first()
    if existing_fdr:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An FDR with number '{deposit_in.fdr_number}' is already registered in the system."
        )

    new_deposit = Deposit(
        fdr_number=deposit_in.fdr_number.strip().upper(),
        amount=deposit_in.amount,
        bank_name=deposit_in.bank_name.strip(),
        branch_name=deposit_in.branch_name.strip() if deposit_in.branch_name else None,
        ifsc_code=deposit_in.ifsc_code.strip().upper() if deposit_in.ifsc_code else None,
        issue_date=deposit_in.issue_date,
        maturity_date=deposit_in.maturity_date,
        contract_reference=deposit_in.contract_reference.strip() if deposit_in.contract_reference else None,
        status=DepositStatus.PENDING_VERIFICATION,
        institution_id=target_institution_id,
        submitted_by_id=current_user.id
    )

    db.add(new_deposit)
    db.commit()
    db.refresh(new_deposit)

    record_audit_log(
        db=db,
        deposit_id=new_deposit.id,
        action="DEPOSIT_SUBMITTED",
        actor_id=current_user.id,
        details=f"FDR {new_deposit.fdr_number} submitted for amount INR {new_deposit.amount}."
    )
    
    return db.query(Deposit).options(
        joinedload(Deposit.institution),
        joinedload(Deposit.submitted_by),
        joinedload(Deposit.verified_by)
    ).filter(Deposit.id == new_deposit.id).first()

@router.get("/{deposit_id}", response_model=DepositResponse)
def get_deposit(
    deposit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves details for a single FDR deposit.
    Institution users can only view their own FDRs.
    """
    deposit = db.query(Deposit).options(
        joinedload(Deposit.institution),
        joinedload(Deposit.submitted_by),
        joinedload(Deposit.verified_by)
    ).filter(Deposit.id == deposit_id).first()

    if not deposit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FDR deposit not found."
        )

    if current_user.role == UserRole.INSTITUTION and deposit.institution_id != current_user.institution_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view deposits belonging to other institutions."
        )

    return deposit

@router.patch("/{deposit_id}/status", response_model=DepositResponse)
def update_deposit_status(
    deposit_id: int,
    status_update: DepositStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_officer_or_admin)
):
    """
    Updates the verification or lifecycle status of an FDR deposit.
    Restricted to OFFICER and ADMIN roles.
    """
    deposit = db.query(Deposit).filter(Deposit.id == deposit_id).first()
    if not deposit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FDR deposit not found."
        )

    old_status = deposit.status
    deposit.status = status_update.status
    deposit.verified_by_id = current_user.id
    deposit.verified_at = utc_now()
    if status_update.verification_remarks is not None:
        deposit.verification_remarks = status_update.verification_remarks.strip()

    db.commit()
    db.refresh(deposit)

    record_audit_log(
        db=db,
        deposit_id=deposit.id,
        action="STATUS_CHANGED",
        actor_id=current_user.id,
        details=f"Status changed from {old_status.value} to {deposit.status.value} by {current_user.full_name} ({current_user.role.value}). Remarks: {status_update.verification_remarks or 'None'}"
    )

    return db.query(Deposit).options(
        joinedload(Deposit.institution),
        joinedload(Deposit.submitted_by),
        joinedload(Deposit.verified_by)
    ).filter(Deposit.id == deposit.id).first()

# =========================================================================
# Phase 2 Workflow Endpoints: Renewal, Release, Forfeiture, Decisions
# =========================================================================

# --------------------------------------------------------------------------- #
# Phase 2 request endpoints, kept for compatibility.
#
# They no longer implement their own rules: each one calls the unified approval
# workflow in routers/approval_requests.py, so an FDR can only ever change state
# through one set of rules, one request record and one audit trail. New clients
# should use /api/requests/*.
# --------------------------------------------------------------------------- #
def _deposit_out(db: Session, deposit_id: int):
    db.expire_all()
    return db.query(Deposit).options(
        joinedload(Deposit.institution),
        joinedload(Deposit.submitted_by),
        joinedload(Deposit.verified_by)
    ).filter(Deposit.id == deposit_id).first()


@router.post("/{deposit_id}/renewal-request", response_model=DepositResponse, deprecated=True,
             summary="Deprecated: use POST /api/requests/renewal")
def request_fdr_renewal(
    deposit_id: int,
    renewal_in: DepositRenewalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wf.submit_renewal_request(
        wf.RenewalRequestCreate(deposit_id=deposit_id, requested_tenure_months=renewal_in.requested_tenure_months,
                                description=renewal_in.remarks),
        db=db, current_user=current_user)
    return _deposit_out(db, deposit_id)


@router.post("/{deposit_id}/release-request", response_model=DepositResponse, deprecated=True,
             summary="Deprecated: use POST /api/requests/release")
def request_fdr_release(
    deposit_id: int,
    release_in: DepositReleaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wf.submit_release_request(
        wf.ReleaseRequestCreate(deposit_id=deposit_id, justification=release_in.justification,
                                compliance_reference=release_in.compliance_reference),
        db=db, current_user=current_user)
    return _deposit_out(db, deposit_id)


@router.post("/{deposit_id}/forfeiture-request", response_model=DepositResponse, deprecated=True,
             summary="Deprecated: use POST /api/requests/forfeiture")
def request_fdr_forfeiture(
    deposit_id: int,
    forfeiture_in: DepositForfeitureRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wf.submit_forfeiture_request(
        wf.ForfeitureRequestCreate(deposit_id=deposit_id, violation_reason=forfeiture_in.violation_reason,
                                   statutory_clause=forfeiture_in.statutory_clause),
        db=db, current_user=current_user)
    return _deposit_out(db, deposit_id)


@router.post("/{deposit_id}/action-decision", response_model=DepositResponse, deprecated=True,
             summary="Deprecated: use PATCH /api/requests/{id}/approve or /reject")
def decide_action_request(
    deposit_id: int,
    decision_in: DepositActionDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_officer_or_admin)
):
    """Approves or rejects the open request on this FDR through the unified workflow."""
    if not db.query(Deposit.id).filter(Deposit.id == deposit_id).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FDR deposit not found.")
    open_request = db.query(wf.ApprovalRequest).filter(
        wf.ApprovalRequest.deposit_id == deposit_id,
        wf.ApprovalRequest.status.in_(wf.OPEN_STATES),
    ).first()
    if not open_request:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="This FDR has no open approval request to decide.")
    if decision_in.decision == "APPROVE":
        wf.approve_request(
            open_request.id,
            wf.ApprovalDecisionRequest(decision_remarks=decision_in.decision_remarks,
                                       extended_maturity_date=decision_in.extended_maturity_date),
            db=db, current_user=current_user)
    else:
        reason = (decision_in.decision_remarks or "").strip()
        if len(reason) < 3:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail="A rejection reason is required in decision_remarks.")
        wf.reject_request(open_request.id, wf.RejectionDecisionRequest(rejection_reason=reason),
                          db=db, current_user=current_user)
    return _deposit_out(db, deposit_id)


@router.get("/{deposit_id}/documents", response_model=List[DocumentResponse], summary="List documents attached to a deposit")
def list_deposit_documents(
    deposit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    deposit = db.query(Deposit).filter(Deposit.id == deposit_id).first()
    if not deposit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deposit with ID {deposit_id} not found."
        )

    if current_user.role == UserRole.INSTITUTION:
        if deposit.institution_id != current_user.institution_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot access documents belonging to another institution's FDR."
            )

    docs = db.query(Document).filter(Document.deposit_id == deposit.id).order_by(Document.upload_timestamp.desc()).all()
    return [
        DocumentResponse(
            id=d.id,
            deposit_id=d.deposit_id,
            institution_id=d.institution_id,
            contract_id=d.contract_id,
            original_filename=d.original_filename,
            document_type=d.document_type,
            file_size=d.file_size,
            mime_type=d.mime_type,
            upload_timestamp=d.upload_timestamp,
            uploaded_by_id=d.uploaded_by_id,
            verification_status=d.verification_status,
            verified_by_id=d.verified_by_id,
            verification_timestamp=d.verification_timestamp,
            rejection_reason=d.rejection_reason,
            download_url=f"/api/documents/{d.id}/download"
        )
        for d in docs
    ]
