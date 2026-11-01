from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.services.reminder_service import process_maturity_reminders
from backend.app.auth.dependencies import require_officer_or_admin
from backend.app.config import settings
from backend.app.models.user import User

router = APIRouter(prefix="/reminders", tags=["Automated Reminders & Scheduler"])

@router.post("/process")
def trigger_reminders(
    reference_date: Optional[date] = Query(
        None,
        description="Optional controlled reference date for testing reminder generation (defaults to today)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_officer_or_admin)
):
    """
    Officer/Admin only. Triggers the maturity reminder scanner and lifecycle status transition engine.
    Idempotent: prevents duplicate notifications for the same FDR and reminder milestone.
    """
    if reference_date is not None and not settings.ALLOW_REMINDER_DATE_OVERRIDE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="reference_date override is disabled. Set ALLOW_REMINDER_DATE_OVERRIDE=true for demos/testing."
        )
    summary = process_maturity_reminders(db, as_of_date=reference_date)
    return {
        "status": "success",
        "triggered_by": current_user.email,
        "summary": summary
    }
