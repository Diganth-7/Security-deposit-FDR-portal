from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from backend.app.database import get_db
from backend.app.models.contract import Contract, ContractStatus
from backend.app.models.deposit import Deposit, DepositStatus
from backend.app.models.institution import Institution
from backend.app.models.user import User, UserRole
from backend.app.schemas.contract import (
    ContractCreate,
    ContractUpdate,
    ContractResponse,
)
from backend.app.schemas.deposit import DepositResponse
from backend.app.auth.dependencies import (
    get_current_user,
    require_officer_or_admin,
    require_role,
)
from backend.app.services.audit_service import record_audit_log
from backend.app.services.contract_service import compute_contract_metrics
from backend.app.utils.clock import utc_now

router = APIRouter(prefix="/contracts", tags=["Contracts & Statutory Agreements"])

def format_contract_response(contract: Contract) -> ContractResponse:
    metrics = compute_contract_metrics(contract)
    resp = ContractResponse.model_validate(contract)
    resp.total_deposited_amount = metrics["total_deposited_amount"]
    resp.is_deposit_sufficient = metrics["is_deposit_sufficient"]
    resp.deposit_shortfall = metrics["deposit_shortfall"]
    resp.linked_deposits_count = metrics["linked_deposits_count"]
    return resp

CLOSING_STATUSES = (ContractStatus.COMPLETED, ContractStatus.EXPIRED, ContractStatus.TERMINATED)


def _require_authority_for_closing(user: User, new_status) -> None:
    """Closing a contract unlocks deposit release/forfeiture rules, so institutions may not do it."""
    if new_status in CLOSING_STATUSES and user.role == UserRole.INSTITUTION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an AICTE officer or administrator can mark a contract COMPLETED, EXPIRED or TERMINATED.",
        )


def _contract_snapshot(c: Contract) -> dict:
    return {
        "contract_number": c.contract_number, "title": c.title, "contract_type": c.contract_type,
        "contract_amount": c.contract_amount, "required_deposit_amount": c.required_deposit_amount,
        "start_date": c.start_date, "end_date": c.end_date, "status": c.status,
    }


@router.post("", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
def create_contract(
    contract_in: ContractCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Registers a new statutory contract or institutional agreement.
    - Institutions register contracts for their own institution.
    - Admins can register on behalf of any institution.
    - Officers cannot register contracts directly.
    """
    if current_user.role == UserRole.OFFICER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Officers cannot create contracts. Only Institutions and Admins are permitted."
        )

    target_institution_id = contract_in.institution_id
    if current_user.role == UserRole.INSTITUTION:
        if not current_user.institution_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your account is not associated with an AICTE approved institution."
            )
        target_institution_id = current_user.institution_id
    elif not target_institution_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Institution ID is required when registering a contract as Administrator."
        )

    # Verify institution exists
    inst = db.query(Institution).filter(Institution.id == target_institution_id).first()
    if not inst:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Institution with ID {target_institution_id} does not exist."
        )

    # Check for unique contract reference number
    existing = db.query(Contract).filter(
        Contract.contract_number == contract_in.contract_number.strip().upper()
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A contract with reference number '{contract_in.contract_number}' already exists."
        )

    _require_authority_for_closing(current_user, contract_in.status)

    new_contract = Contract(
        contract_number=contract_in.contract_number.strip().upper(),
        title=contract_in.title.strip(),
        description=contract_in.description.strip() if contract_in.description else None,
        institution_id=target_institution_id,
        contract_type=contract_in.contract_type.strip(),
        contract_amount=contract_in.contract_amount,
        required_deposit_amount=contract_in.required_deposit_amount,
        start_date=contract_in.start_date,
        end_date=contract_in.end_date,
        status=contract_in.status or ContractStatus.DRAFT
    )

    db.add(new_contract)
    db.flush()
    record_audit_log(
        db, action="CONTRACT_CREATED", actor_id=current_user.id, entity_type="CONTRACT", entity_id=new_contract.id,
        institution_id=target_institution_id, details=f"Contract {new_contract.contract_number} created.",
        after=_contract_snapshot(new_contract), commit=False,
    )
    db.commit()
    db.refresh(new_contract)

    # Reload with institution and deposits
    contract = db.query(Contract).options(
        joinedload(Contract.institution),
        joinedload(Contract.deposits)
    ).filter(Contract.id == new_contract.id).first()

    return format_contract_response(contract)

@router.get("", response_model=List[ContractResponse])
def list_contracts(
    status_filter: Optional[ContractStatus] = Query(None, alias="status", description="Filter by Contract Status"),
    institution_id: Optional[int] = Query(None, description="Filter by Institution ID (Admin/Officer only)"),
    search: Optional[str] = Query(None, description="Search by contract number, title, or type"),
    insufficient_only: bool = Query(False, description="Filter only contracts with insufficient security deposit"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists institutional contracts.
    - Institutions can only view their own contracts.
    - Officers and Admins can view pan-India contracts.
    """
    query = db.query(Contract).options(
        joinedload(Contract.institution),
        joinedload(Contract.deposits)
    )

    # Role scoping
    if current_user.role == UserRole.INSTITUTION:
        if not current_user.institution_id:
            return []
        query = query.filter(Contract.institution_id == current_user.institution_id)
    elif institution_id:
        query = query.filter(Contract.institution_id == institution_id)

    if status_filter:
        query = query.filter(Contract.status == status_filter)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Contract.contract_number.ilike(search_pattern)) |
            (Contract.title.ilike(search_pattern)) |
            (Contract.contract_type.ilike(search_pattern))
        )

    contracts = query.order_by(Contract.created_at.desc()).all()

    formatted_list = [format_contract_response(c) for c in contracts]

    if insufficient_only:
        formatted_list = [c for c in formatted_list if not c.is_deposit_sufficient]

    return formatted_list

@router.get("/{contract_id}", response_model=ContractResponse)
def get_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves full details for a contract including security deposit sufficiency.
    """
    contract = db.query(Contract).options(
        joinedload(Contract.institution),
        joinedload(Contract.deposits)
    ).filter(Contract.id == contract_id).first()

    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found."
        )

    if current_user.role == UserRole.INSTITUTION and contract.institution_id != current_user.institution_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view contracts of other institutions."
        )

    return format_contract_response(contract)

@router.put("/{contract_id}", response_model=ContractResponse)
def update_contract(
    contract_id: int,
    update_in: ContractUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Updates contract information.
    - Institutions can only update their own contracts.
    - Officers and Admins can update institutional contracts.
    - Preserves existing FDR records linked to the contract.
    """
    contract = db.query(Contract).options(
        joinedload(Contract.institution),
        joinedload(Contract.deposits)
    ).filter(Contract.id == contract_id).first()

    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found."
        )

    if current_user.role == UserRole.INSTITUTION and contract.institution_id != current_user.institution_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to modify contracts of other institutions."
        )

    # Validate updated dates against existing dates
    new_start = update_in.start_date or contract.start_date
    new_end = update_in.end_date or contract.end_date
    if new_end <= new_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Contract end date must be strictly after the start date."
        )

    if update_in.status is not None and update_in.status != contract.status:
        _require_authority_for_closing(current_user, update_in.status)
    if current_user.role == UserRole.INSTITUTION and contract.status in CLOSING_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This contract is closed; only an AICTE officer or administrator can change it.",
        )
    before = _contract_snapshot(contract)

    # Apply updates
    if update_in.title is not None:
        contract.title = update_in.title.strip()
    if update_in.description is not None:
        contract.description = update_in.description.strip()
    if update_in.contract_type is not None:
        contract.contract_type = update_in.contract_type.strip()
    if update_in.contract_amount is not None:
        contract.contract_amount = update_in.contract_amount
    if update_in.required_deposit_amount is not None:
        contract.required_deposit_amount = update_in.required_deposit_amount
    if update_in.start_date is not None:
        contract.start_date = update_in.start_date
    if update_in.end_date is not None:
        contract.end_date = update_in.end_date
    if update_in.status is not None:
        contract.status = update_in.status

    contract.updated_at = utc_now()
    after = _contract_snapshot(contract)
    record_audit_log(
        db, action="CONTRACT_STATUS_CHANGED" if before["status"] != after["status"] else "CONTRACT_UPDATED",
        actor_id=current_user.id, entity_type="CONTRACT", entity_id=contract.id,
        institution_id=contract.institution_id, details=f"Contract {contract.contract_number} updated.",
        before=before, after=after, commit=False,
    )
    db.commit()
    db.refresh(contract)

    return format_contract_response(contract)

@router.get("/{contract_id}/deposits", response_model=List[DepositResponse])
def get_contract_deposits(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists all Fixed Deposit Receipts (FDRs) linked to a specific contract.
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found."
        )

    if current_user.role == UserRole.INSTITUTION and contract.institution_id != current_user.institution_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view deposits for this contract."
        )

    deposits = db.query(Deposit).options(
        joinedload(Deposit.institution),
        joinedload(Deposit.submitted_by),
        joinedload(Deposit.verified_by)
    ).filter(Deposit.contract_id == contract_id).all()

    return deposits

@router.post("/{contract_id}/deposits/{deposit_id}", response_model=ContractResponse)
def link_deposit_to_contract(
    contract_id: int,
    deposit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Links an existing FDR deposit to a contract.
    Enforces business rules:
    - Both contract and deposit must exist.
    - Both must belong to the exact same institution.
    - Cannot link a REJECTED deposit.
    - Recomputes total security deposit and sufficiency metrics.
    """
    contract = db.query(Contract).options(
        joinedload(Contract.institution),
        joinedload(Contract.deposits)
    ).filter(Contract.id == contract_id).first()

    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found."
        )

    deposit = db.query(Deposit).filter(Deposit.id == deposit_id).first()
    if not deposit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deposit not found."
        )

    # Authorization check
    if current_user.role == UserRole.INSTITUTION and contract.institution_id != current_user.institution_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot link deposits to contracts of other institutions."
        )

    # Cross-institution linking prohibition
    if deposit.institution_id != contract.institution_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mismatched institutions: Deposit belongs to institution ID {deposit.institution_id}, but contract belongs to {contract.institution_id}."
        )

    # Status check
    if deposit.status == DepositStatus.REJECTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot link a REJECTED FDR deposit to a contract."
        )

    # Link deposit
    deposit.contract_id = contract.id
    deposit.contract_reference = contract.contract_number
    db.commit()

    # Record Audit Log
    record_audit_log(
        db=db,
        deposit_id=deposit.id,
        action="DEPOSIT_LINKED_TO_CONTRACT",
        actor_id=current_user.id,
        details=f"FDR {deposit.fdr_number} (Amount: INR {deposit.amount}) linked to Contract {contract.contract_number} ({contract.title})."
    )

    # Refresh contract and return updated metrics
    db.refresh(contract)
    return format_contract_response(contract)

@router.delete("/{contract_id}")
def delete_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Deletes a contract record only if no financial records/deposits are linked.
    Enforces Rule: Do not delete contracts that have linked financial records; use appropriate status changes instead.
    """
    contract = db.query(Contract).options(joinedload(Contract.deposits)).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found."
        )

    if current_user.role == UserRole.INSTITUTION and contract.institution_id != current_user.institution_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to delete contracts of other institutions."
        )

    # Prevent deletion if linked financial records exist
    if contract.deposits and len(contract.deposits) > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete contract with linked financial FDR records. Please update contract status to TERMINATED or COMPLETED instead."
        )

    snapshot = _contract_snapshot(contract)
    institution_id = contract.institution_id
    db.delete(contract)
    record_audit_log(
        db, action="CONTRACT_DELETED", actor_id=current_user.id, entity_type="CONTRACT", entity_id=contract_id,
        institution_id=institution_id, details=f"Contract #{contract_id} deleted (no linked FDRs).",
        before=snapshot, commit=False,
    )
    db.commit()

    return {"status": "success", "message": f"Contract #{contract_id} successfully deleted."}
