import enum
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.database import Base
from backend.app.utils.clock import utc_now

class DepositStatus(str, enum.Enum):
    # Phase 1 statuses
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFIED = "VERIFIED"
    ACTIVE = "ACTIVE"
    MATURED = "MATURED"
    RELEASED = "RELEASED"
    REJECTED = "REJECTED"
    
    # Phase 2 maturity tracking & lifecycle statuses
    MATURITY_APPROACHING = "MATURITY_APPROACHING"
    MATURED_ACTION_REQUIRED = "MATURED_ACTION_REQUIRED"
    RENEWAL_REQUESTED = "RENEWAL_REQUESTED"
    RELEASE_REQUESTED = "RELEASE_REQUESTED"
    FORFEITURE_REQUESTED = "FORFEITURE_REQUESTED"
    CLOSED = "CLOSED"

class Deposit(Base):
    __tablename__ = "deposits"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    fdr_number = Column(String(100), unique=True, index=True, nullable=False)
    amount = Column(Float, nullable=False)
    bank_name = Column(String(255), nullable=False)
    branch_name = Column(String(255), nullable=True)
    ifsc_code = Column(String(50), nullable=True)
    issue_date = Column(Date, nullable=False)
    maturity_date = Column(Date, nullable=False)
    status = Column(Enum(DepositStatus), default=DepositStatus.PENDING_VERIFICATION, nullable=False, index=True)
    
    # Associated contract or statutory approval reference
    contract_reference = Column(String(100), nullable=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Institution that owns this deposit
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    
    # User who submitted the FDR
    submitted_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    
    # Officer who verified / inspected the FDR
    verified_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verification_remarks = Column(Text, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    institution = relationship("Institution", back_populates="deposits")
    contract = relationship("Contract", back_populates="deposits")
    submitted_by = relationship("User", foreign_keys=[submitted_by_id], back_populates="submitted_deposits")
    verified_by = relationship("User", foreign_keys=[verified_by_id], back_populates="verified_deposits")
    notifications = relationship("Notification", back_populates="deposit", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="deposit", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="deposit", cascade="all, delete-orphan")
    approval_requests = relationship("ApprovalRequest", back_populates="deposit", cascade="all, delete-orphan")

