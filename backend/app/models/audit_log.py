from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, event
from sqlalchemy.orm import relationship
from backend.app.database import Base
from backend.app.utils.clock import utc_now


class AuditLog(Base):
    """
    Append-only record of who did what to which entity.

    Rows are never updated or deleted by the application: ORM-level guards below
    raise if code tries. (A database administrator can still change rows; for
    stronger guarantees add a PostgreSQL trigger or ship logs to WORM storage.)
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Actor (None for automated/system jobs)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_role = Column(String(30), nullable=True)

    action = Column(String(100), nullable=False, index=True)

    # Generic target of the action (DEPOSIT, CONTRACT, DOCUMENT, APPROVAL_REQUEST, USER, ...)
    entity_type = Column(String(50), nullable=True, index=True)
    entity_id = Column(Integer, nullable=True, index=True)

    # Kept for FDR-centric history. Not cascaded: audit rows must outlive the FDR.
    deposit_id = Column(Integer, ForeignKey("deposits.id", ondelete="SET NULL"), nullable=True, index=True)
    # Owning institution, used to scope what institution users may see.
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True, index=True)

    details = Column(Text, nullable=True)
    before_data = Column(Text, nullable=True)  # JSON, secrets removed
    after_data = Column(Text, nullable=True)   # JSON, secrets removed
    correlation_id = Column(String(64), nullable=True, index=True)

    timestamp = Column(DateTime, default=utc_now, nullable=False, index=True)

    actor = relationship("User", foreign_keys=[actor_id])
    deposit = relationship("Deposit", back_populates="audit_logs")


@event.listens_for(AuditLog, "before_update")
def _block_audit_update(mapper, connection, target):
    raise PermissionError("Audit log entries are append-only and cannot be modified.")


@event.listens_for(AuditLog, "before_delete")
def _block_audit_delete(mapper, connection, target):
    raise PermissionError("Audit log entries are append-only and cannot be deleted.")
