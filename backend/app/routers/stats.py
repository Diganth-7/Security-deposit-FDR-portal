from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.database import get_db
from backend.app.models.deposit import Deposit, DepositStatus
from backend.app.models.institution import Institution
from backend.app.models.user import User, UserRole
from backend.app.auth.dependencies import get_current_user

router = APIRouter(prefix="/stats", tags=["Dashboard Statistics"])

@router.get("/dashboard")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns high-level statistics for the dashboard.
    Scoping:
    - INSTITUTION: Stats only for their institution.
    - ADMIN & OFFICER: Pan-India aggregate stats.
    """
    base_query = db.query(Deposit)
    if current_user.role == UserRole.INSTITUTION:
        if not current_user.institution_id:
            return {
                "total_count": 0,
                "total_amount": 0.0,
                "pending_count": 0,
                "verified_count": 0,
                "active_count": 0,
                "matured_count": 0,
                "institutions_count": 0,
                "role": current_user.role.value
            }
        base_query = base_query.filter(Deposit.institution_id == current_user.institution_id)

    total_count = base_query.count()
    total_amount = base_query.with_entities(func.coalesce(func.sum(Deposit.amount), 0.0)).scalar()

    pending_count = base_query.filter(Deposit.status == DepositStatus.PENDING_VERIFICATION).count()
    verified_count = base_query.filter(Deposit.status == DepositStatus.VERIFIED).count()
    active_count = base_query.filter(Deposit.status == DepositStatus.ACTIVE).count()
    matured_count = base_query.filter(Deposit.status == DepositStatus.MATURED).count()
    rejected_count = base_query.filter(Deposit.status == DepositStatus.REJECTED).count()

    institutions_count = db.query(Institution).count()

    return {
        "total_count": total_count,
        "total_amount": float(total_amount),
        "pending_count": pending_count,
        "verified_count": verified_count,
        "active_count": active_count,
        "matured_count": matured_count,
        "rejected_count": rejected_count,
        "institutions_count": institutions_count,
        "role": current_user.role.value,
        "user_name": current_user.full_name
    }
