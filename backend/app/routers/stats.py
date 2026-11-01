from datetime import date, timedelta
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
    Returns high-level statistics for the dashboard, extended with Phase 2 maturity metrics.
    Scoping:
    - INSTITUTION: Stats only for their institution.
    - ADMIN & OFFICER: Pan-India aggregate stats.
    """
    today = date.today()
    in_30_days = today + timedelta(days=30)
    in_7_days = today + timedelta(days=7)
    in_1_day = today + timedelta(days=1)

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
                "rejected_count": 0,
                "total_active_fdrs": 0,
                "maturing_within_30_days": 0,
                "maturing_within_7_days": 0,
                "maturing_within_1_day": 0,
                "matured_action_required": 0,
                "renewal_requests_pending": 0,
                "release_requests_pending": 0,
                "forfeiture_requests_pending": 0,
                "institutions_count": 0,
                "role": current_user.role.value,
                "user_name": current_user.full_name
            }
        base_query = base_query.filter(Deposit.institution_id == current_user.institution_id)

    total_count = base_query.count()
    total_amount = base_query.with_entities(func.coalesce(func.sum(Deposit.amount), 0.0)).scalar()

    # Base statuses
    pending_count = base_query.filter(Deposit.status == DepositStatus.PENDING_VERIFICATION).count()
    verified_count = base_query.filter(Deposit.status == DepositStatus.VERIFIED).count()
    active_count = base_query.filter(Deposit.status == DepositStatus.ACTIVE).count()
    matured_count = base_query.filter(Deposit.status.in_([DepositStatus.MATURED, DepositStatus.MATURED_ACTION_REQUIRED])).count()
    rejected_count = base_query.filter(Deposit.status == DepositStatus.REJECTED).count()

    # Phase 2 Maturity & Request Metrics
    total_active_fdrs = base_query.filter(
        Deposit.status.in_([
            DepositStatus.ACTIVE,
            DepositStatus.MATURITY_APPROACHING,
            DepositStatus.VERIFIED
        ])
    ).count()

    # Active or verified FDRs within maturity windows
    active_scope_statuses = [
        DepositStatus.ACTIVE,
        DepositStatus.MATURITY_APPROACHING,
        DepositStatus.VERIFIED
    ]

    maturing_within_30_days = base_query.filter(
        Deposit.status.in_(active_scope_statuses),
        Deposit.maturity_date >= today,
        Deposit.maturity_date <= in_30_days
    ).count()

    maturing_within_7_days = base_query.filter(
        Deposit.status.in_(active_scope_statuses),
        Deposit.maturity_date >= today,
        Deposit.maturity_date <= in_7_days
    ).count()

    maturing_within_1_day = base_query.filter(
        Deposit.status.in_(active_scope_statuses),
        Deposit.maturity_date >= today,
        Deposit.maturity_date <= in_1_day
    ).count()

    matured_action_required = base_query.filter(
        Deposit.status == DepositStatus.MATURED_ACTION_REQUIRED
    ).count()

    renewal_requests_pending = base_query.filter(
        Deposit.status == DepositStatus.RENEWAL_REQUESTED
    ).count()

    release_requests_pending = base_query.filter(
        Deposit.status == DepositStatus.RELEASE_REQUESTED
    ).count()

    forfeiture_requests_pending = base_query.filter(
        Deposit.status == DepositStatus.FORFEITURE_REQUESTED
    ).count()

    institutions_count = db.query(Institution).count()

    return {
        "total_count": total_count,
        "total_amount": float(total_amount),
        "pending_count": pending_count,
        "verified_count": verified_count,
        "active_count": active_count,
        "matured_count": matured_count,
        "rejected_count": rejected_count,
        "total_active_fdrs": total_active_fdrs,
        "maturing_within_30_days": maturing_within_30_days,
        "maturing_within_7_days": maturing_within_7_days,
        "maturing_within_1_day": maturing_within_1_day,
        "matured_action_required": matured_action_required,
        "renewal_requests_pending": renewal_requests_pending,
        "release_requests_pending": release_requests_pending,
        "forfeiture_requests_pending": forfeiture_requests_pending,
        "institutions_count": institutions_count,
        "role": current_user.role.value,
        "user_name": current_user.full_name
    }
