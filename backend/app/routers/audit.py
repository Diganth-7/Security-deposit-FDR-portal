"""Read-only audit trail API. There is intentionally no endpoint that edits or deletes entries."""
from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from backend.app.auth.dependencies import require_role
from backend.app.database import get_db
from backend.app.models.audit_log import AuditLog
from backend.app.models.user import User, UserRole
from backend.app.schemas.audit_log import AuditLogPage, AuditLogResponse

router = APIRouter(prefix="/audit-logs", tags=["Audit Trail"])

# Officers and administrators only: institutions never read the audit trail.
_viewer = require_role([UserRole.OFFICER, UserRole.ADMIN])

ENTITY_TYPES = {"DEPOSIT", "CONTRACT", "DOCUMENT", "APPROVAL_REQUEST", "USER", "REPORT"}


def _day_start(d: date) -> datetime:
    return datetime.combine(d, time.min)


def _query(db: Session):
    return db.query(AuditLog).options(joinedload(AuditLog.actor))


def _page(query, limit: int, offset: int) -> AuditLogPage:
    total = query.count()
    rows = query.order_by(AuditLog.timestamp.desc(), AuditLog.id.desc()).offset(offset).limit(limit).all()
    return AuditLogPage(items=[AuditLogResponse.from_row(r) for r in rows], total=total, limit=limit, offset=offset)


@router.get("", response_model=AuditLogPage, summary="Search the audit trail")
def list_audit_logs(
    entity_type: Optional[str] = Query(None, description="DEPOSIT, CONTRACT, DOCUMENT, APPROVAL_REQUEST or USER"),
    entity_id: Optional[int] = Query(None, ge=1),
    action: Optional[str] = Query(None, max_length=100),
    actor_id: Optional[int] = Query(None, ge=1),
    institution_id: Optional[int] = Query(None, ge=1),
    deposit_id: Optional[int] = Query(None, ge=1),
    correlation_id: Optional[str] = Query(None, max_length=64),
    date_from: Optional[date] = Query(None, description="Inclusive start date"),
    date_to: Optional[date] = Query(None, description="Inclusive end date"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(_viewer),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="date_from must not be after date_to.")
    q = _query(db)
    if entity_type:
        et = entity_type.upper()
        if et not in ENTITY_TYPES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=f"entity_type must be one of {sorted(ENTITY_TYPES)}.")
        q = q.filter(AuditLog.entity_type == et)
    for column, value in ((AuditLog.entity_id, entity_id), (AuditLog.action, action.upper() if action else None),
                          (AuditLog.actor_id, actor_id), (AuditLog.institution_id, institution_id),
                          (AuditLog.deposit_id, deposit_id), (AuditLog.correlation_id, correlation_id)):
        if value is not None:
            q = q.filter(column == value)
    if date_from:
        q = q.filter(AuditLog.timestamp >= _day_start(date_from))
    if date_to:
        q = q.filter(AuditLog.timestamp < _day_start(date_to + timedelta(days=1)))
    return _page(q, limit, offset)


@router.get("/{entity_type}/{entity_id}", response_model=AuditLogPage, summary="History of one record")
def entity_history(
    entity_type: str,
    entity_id: int,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(_viewer),
):
    et = entity_type.upper()
    if et not in ENTITY_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"entity_type must be one of {sorted(ENTITY_TYPES)}.")
    q = _query(db).filter(AuditLog.entity_type == et, AuditLog.entity_id == entity_id)
    if et == "DEPOSIT":  # an FDR's history also includes its documents' and requests' events
        q = _query(db).filter((AuditLog.entity_type == "DEPOSIT") & (AuditLog.entity_id == entity_id)
                              | (AuditLog.deposit_id == entity_id))
    return _page(q, limit, offset)
