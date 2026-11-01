from typing import Optional
from sqlalchemy.orm import Session
from backend.app.models.audit_log import AuditLog

def record_audit_log(
    db: Session,
    deposit_id: int,
    action: str,
    actor_id: Optional[int] = None,
    details: Optional[str] = None
) -> AuditLog:
    """
    Creates an immutable audit trail entry for statutory compliance.
    """
    log_entry = AuditLog(
        deposit_id=deposit_id,
        action=action,
        actor_id=actor_id,
        details=details
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry
