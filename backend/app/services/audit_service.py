import json
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.app.models.audit_log import AuditLog
from backend.app.utils.context import get_request_id

logger = logging.getLogger("aicte_fdr.audit")

_SECRET_WORDS = ("password", "secret", "token", "hash", "authorization", "api_key")


def _clean(value: Any) -> Any:
    """Make a value JSON-safe and drop anything that looks like a secret."""
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if any(w in str(k).lower() for w in _SECRET_WORDS) else _clean(v))
                for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_clean(v) for v in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "value") and not isinstance(value, (str, int, float, bool)):
        return value.value  # Enum
    return value


def _dump(value: Optional[dict]) -> Optional[str]:
    return None if value is None else json.dumps(_clean(value), sort_keys=True, default=str)


def record_audit_log(
    db: Session,
    deposit_id: Optional[int] = None,
    action: str = "",
    actor_id: Optional[int] = None,
    details: Optional[str] = None,
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    institution_id: Optional[int] = None,
    actor_role: Optional[str] = None,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
    commit: bool = True,
) -> AuditLog:
    """
    Appends one audit entry. The original call style
    ``record_audit_log(db, deposit_id, action, actor_id, details)`` still works.

    Missing context is filled in automatically: the actor's role, the FDR's
    institution, the entity (an FDR when only deposit_id is given) and the
    current request's correlation ID.
    """
    if actor_id is not None and actor_role is None:
        from backend.app.models.user import User
        actor = db.get(User, actor_id)
        if actor is not None:
            actor_role = actor.role.value if hasattr(actor.role, "value") else str(actor.role)
            if institution_id is None and entity_type in (None, "USER"):
                institution_id = actor.institution_id
    if deposit_id is not None:
        if entity_type is None:
            entity_type, entity_id = "DEPOSIT", deposit_id
        if institution_id is None:
            from backend.app.models.deposit import Deposit
            dep = db.get(Deposit, deposit_id)
            institution_id = dep.institution_id if dep else None

    entry = AuditLog(
        deposit_id=deposit_id,
        action=action,
        actor_id=actor_id,
        actor_role=actor_role,
        entity_type=entity_type,
        entity_id=entity_id,
        institution_id=institution_id,
        details=details,
        before_data=_dump(before),
        after_data=_dump(after),
        correlation_id=get_request_id(),
    )
    db.add(entry)
    if commit:
        db.commit()
        db.refresh(entry)
    else:
        db.flush()
    return entry
