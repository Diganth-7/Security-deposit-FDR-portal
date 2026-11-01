from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.services.reminder_service import process_maturity_reminders
from backend.app.auth.dependencies import get_current_user
from backend.app.models.user import User

router = APIRouter(prefix="/reminders", tags=["Automated Reminders & Scheduler"])

@router.post("/process")
def trigger_reminders(
    reference_date: Optional[date] = Query(
        None,
        description="Optional controlled reference date for testing reminder generation (defaults to today)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Triggers the maturity reminder scanner and lifecycle status transition engine.
    Idempotent: prevents duplicate notifications for the same FDR and reminder milestone.
    """
    summary = process_maturity_reminders(db, as_of_date=reference_date)
    return {
        "status": "success",
        "triggered_by": current_user.email,
        "summary": summary
    }
