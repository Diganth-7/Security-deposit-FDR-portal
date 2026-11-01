import json
from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel


def _load(value: Optional[str]) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except ValueError:
        return None


class AuditLogResponse(BaseModel):
    id: int
    actor_id: Optional[int] = None
    actor_name: Optional[str] = None
    actor_role: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    deposit_id: Optional[int] = None
    institution_id: Optional[int] = None
    details: Optional[str] = None
    before: Optional[Any] = None
    after: Optional[Any] = None
    correlation_id: Optional[str] = None
    timestamp: datetime

    @classmethod
    def from_row(cls, row) -> "AuditLogResponse":
        return cls(
            id=row.id, actor_id=row.actor_id, actor_name=row.actor.full_name if row.actor else None,
            actor_role=row.actor_role, action=row.action, entity_type=row.entity_type, entity_id=row.entity_id,
            deposit_id=row.deposit_id, institution_id=row.institution_id, details=row.details,
            before=_load(row.before_data), after=_load(row.after_data),
            correlation_id=row.correlation_id, timestamp=row.timestamp,
        )


class AuditLogPage(BaseModel):
    items: List[AuditLogResponse]
    total: int
    limit: int
    offset: int
