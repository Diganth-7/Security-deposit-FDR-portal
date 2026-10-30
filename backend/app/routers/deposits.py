from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models.deposit import Deposit, DepositStatus
from app.models.institution import Institution
from app.models.user import User, UserRole
from app.schemas.deposit import DepositCreate, DepositResponse, DepositStatusUpdate
from app.auth.dependencies import (
    get_current_user,
    require_officer_or_admin,
    require_role
)

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
        # Officer/Admin filtering by specific institution
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

@router.post("", response_model=DepositResponse, status_code=status.HTTP_201_CREATED)
def submit_deposit(
    deposit_in: DepositCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submits a new FDR / Security Deposit for verification.
    - Institutions submit FDRs for their own institution.
    - Admins can submit on behalf of any institution.
    - Verification Officers cannot submit deposits.
    """
    if current_user.role == UserRole.OFFICER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verification Officers cannot submit deposits. Their role is restricted to review and verification."
        )

    # Determine target institution
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

    # Verify target institution exists
    inst = db.query(Institution).filter(Institution.id == target_institution_id).first()
    if not inst:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Institution with ID {target_institution_id} does not exist."
        )

    # Check for duplicate FDR number
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
        status=DepositStatus.PENDING_VERIFICATION,
        institution_id=target_institution_id,
        submitted_by_id=current_user.id
    )

    db.add(new_deposit)
    db.commit()
    db.refresh(new_deposit)
    
    # Reload with relationships
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
    Stores officer ID, verification remarks, and timestamp.
    """
    deposit = db.query(Deposit).filter(Deposit.id == deposit_id).first()
    if not deposit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FDR deposit not found."
        )

    deposit.status = status_update.status
    deposit.verified_by_id = current_user.id
    deposit.verified_at = datetime.utcnow()
    if status_update.verification_remarks is not None:
        deposit.verification_remarks = status_update.verification_remarks.strip()

    db.commit()
    db.refresh(deposit)

    return db.query(Deposit).options(
        joinedload(Deposit.institution),
        joinedload(Deposit.submitted_by),
        joinedload(Deposit.verified_by)
    ).filter(Deposit.id == deposit.id).first()
