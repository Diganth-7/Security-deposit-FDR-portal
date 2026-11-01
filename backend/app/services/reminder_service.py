import logging
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from backend.app.models.deposit import Deposit, DepositStatus
from backend.app.models.institution import Institution
from backend.app.models.user import User, UserRole
from backend.app.models.notification import Notification
from backend.app.services.audit_service import record_audit_log

logger = logging.getLogger("aicte_fdr.reminders")

# Reminder milestones specified in requirements
REMINDER_30_DAYS = "REMINDER_30_DAYS"
REMINDER_7_DAYS = "REMINDER_7_DAYS"
REMINDER_1_DAY = "REMINDER_1_DAY"
REMINDER_ON_MATURITY = "REMINDER_ON_MATURITY"
REMINDER_OVERDUE = "REMINDER_OVERDUE"

def get_reminder_spec(days_remaining: int) -> Optional[Dict[str, str]]:
    """
    Returns reminder type and template based on remaining days.
    """
    if days_remaining == 30:
        return {
            "type": REMINDER_30_DAYS,
            "title_template": "FDR {fdr} Maturing in 30 Days",
            "msg_template": "Fixed Deposit Receipt {fdr} issued by {bank} for {inst} will mature in 30 days (on {date}). Please prepare necessary renewal or release compliance documents."
        }
    elif days_remaining == 7:
        return {
            "type": REMINDER_7_DAYS,
            "title_template": "Urgent: FDR {fdr} Maturing in 7 Days",
            "msg_template": "Fixed Deposit Receipt {fdr} for {inst} reaches maturity on {date} (7 days remaining). Action is required to avoid statutory compliance lapses."
        }
    elif days_remaining == 1:
        return {
            "type": REMINDER_1_DAY,
            "title_template": "Critical: FDR {fdr} Matures Tomorrow",
            "msg_template": "Fixed Deposit Receipt {fdr} for {inst} matures tomorrow ({date}). Initiate renewal or release request immediately."
        }
    elif days_remaining == 0:
        return {
            "type": REMINDER_ON_MATURITY,
            "title_template": "Action Required: FDR {fdr} Matured Today",
            "msg_template": "Fixed Deposit Receipt {fdr} for {inst} has reached maturity today ({date}). Joint lien holds; statutory renewal, release, or review action is required."
        }
    elif days_remaining < 0:
        return {
            "type": REMINDER_OVERDUE,
            "title_template": "Overdue Action Required: FDR {fdr} Past Maturity",
            "msg_template": "Fixed Deposit Receipt {fdr} for {inst} matured on {date} ({days} days ago). Status is MATURED_ACTION_REQUIRED."
        }
    return None

def process_maturity_reminders(db: Session, as_of_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Scans all registered FDRs, transitions maturity lifecycle statuses,
    and generates automated in-app notifications without duplicates.
    
    Accepts an optional `as_of_date` parameter to allow testing with controlled dates.
    """
    if as_of_date is None:
        as_of_date = date.today()

    logger.info(f"Processing FDR maturity reminders as of {as_of_date}...")

    # Relevant statuses for tracking: ACTIVE, MATURITY_APPROACHING, VERIFIED, MATURED_ACTION_REQUIRED
    trackable_statuses = [
        DepositStatus.ACTIVE,
        DepositStatus.MATURITY_APPROACHING,
        DepositStatus.VERIFIED,
        DepositStatus.MATURED_ACTION_REQUIRED,
    ]

    deposits = db.query(Deposit).filter(Deposit.status.in_(trackable_statuses)).all()

    reminders_created = 0
    status_transitions = 0

    # Prefetch active officers and admins for notifications
    officers_and_admins = db.query(User).filter(
        User.role.in_([UserRole.OFFICER, UserRole.ADMIN]),
        User.is_active == True
    ).all()

    for dep in deposits:
        days_remaining = (dep.maturity_date - as_of_date).days
        inst_name = dep.institution.name if dep.institution else f"Institution #{dep.institution_id}"

        # 1. Status Transition Business Rules:
        # Rule: A maturity date passing must NOT automatically release or forfeit an FDR.
        # It must move to MATURED_ACTION_REQUIRED.
        if days_remaining <= 0 and dep.status != DepositStatus.MATURED_ACTION_REQUIRED:
            prev_status = dep.status
            dep.status = DepositStatus.MATURED_ACTION_REQUIRED
            status_transitions += 1
            record_audit_log(
                db=db,
                deposit_id=dep.id,
                action="STATUS_CHANGED",
                actor_id=None,
                details=f"FDR reached maturity date ({dep.maturity_date}). Transitioned from {prev_status.value} to MATURED_ACTION_REQUIRED."
            )
        elif 0 < days_remaining <= 30 and dep.status == DepositStatus.ACTIVE:
            dep.status = DepositStatus.MATURITY_APPROACHING
            status_transitions += 1
            record_audit_log(
                db=db,
                deposit_id=dep.id,
                action="STATUS_CHANGED",
                actor_id=None,
                details=f"FDR is within 30 days of maturity ({days_remaining} days remaining). Transitioned to MATURITY_APPROACHING."
            )

        # 2. Evaluate if a reminder milestone applies
        spec = get_reminder_spec(days_remaining)
        if not spec:
            continue

        reminder_type = spec["type"]
        title = spec["title_template"].format(
            fdr=dep.fdr_number,
            date=dep.maturity_date.strftime("%d-%m-%Y")
        )
        message = spec["msg_template"].format(
            fdr=dep.fdr_number,
            bank=dep.bank_name,
            inst=inst_name,
            date=dep.maturity_date.strftime("%d-%m-%Y"),
            days=abs(days_remaining)
        )

        # 3. Deliver notifications to recipients (Institution users + Officers/Admins)
        # Recipients for Institution
        inst_users = db.query(User).filter(
            User.institution_id == dep.institution_id,
            User.role == UserRole.INSTITUTION,
            User.is_active == True
        ).all()

        target_recipients: List[Optional[User]] = list(inst_users) + list(officers_and_admins)
        
        # If no specific institution user exists, add a placeholder recipient (None) scoped to institution_id
        if not inst_users:
            target_recipients.append(None)

        dep_reminders_added = False

        for recipient in target_recipients:
            recip_user_id = recipient.id if recipient else None
            recip_role = recipient.role if recipient else UserRole.INSTITUTION

            # IDEMPOTENCY CHECK:
            # Query if notification already exists for (deposit_id, reminder_type, recipient_user_id)
            existing = db.query(Notification).filter(
                Notification.deposit_id == dep.id,
                Notification.reminder_type == reminder_type,
                Notification.recipient_user_id == recip_user_id
            ).first()

            if existing:
                continue  # Already notified for this milestone

            new_notif = Notification(
                recipient_user_id=recip_user_id,
                recipient_role=recip_role,
                institution_id=dep.institution_id,
                deposit_id=dep.id,
                reminder_type=reminder_type,
                title=title,
                message=message,
                days_remaining=days_remaining,
                is_read=False
            )
            db.add(new_notif)
            reminders_created += 1
            dep_reminders_added = True

        if dep_reminders_added:
            record_audit_log(
                db=db,
                deposit_id=dep.id,
                action="REMINDER_GENERATED",
                actor_id=None,
                details=f"Generated {reminder_type} ({days_remaining} days remaining) for FDR {dep.fdr_number}."
            )

    db.commit()

    return {
        "as_of_date": as_of_date.isoformat(),
        "total_deposits_scanned": len(deposits),
        "reminders_created": reminders_created,
        "status_transitions": status_transitions
    }
