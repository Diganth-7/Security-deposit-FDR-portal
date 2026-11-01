import enum
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, DateTime, Date, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.database import Base

class RequestType(str, enum.Enum):
    RENEWAL = "RENEWAL"
    RELEASE = "RELEASE"
    FORFEITURE = "FORFEITURE"

class RequestStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # FDR Deposit Target
    deposit_id = Column(Integer, ForeignKey("deposits.id", ondelete="CASCADE"), nullable=False, index=True)

    # Submitting Institution
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)

    # Optional Linked Contract
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True, index=True)

    # Request Type and Current Workflow Status
    request_type = Column(Enum(RequestType), nullable=False, index=True)
    status = Column(Enum(RequestStatus), default=RequestStatus.SUBMITTED, nullable=False, index=True)

    # Request Details & Justification
    description = Column(Text, nullable=True)
    supporting_document_ids = Column(String(255), nullable=True)  # e.g., "1,4,7"

    # Specific workflow parameters
    requested_tenure_months = Column(Integer, nullable=True)  # for RENEWAL
    extended_maturity_date = Column(Date, nullable=True)       # for RENEWAL approved extension
    compliance_reference = Column(String(255), nullable=True)  # for RELEASE
    statutory_clause = Column(String(255), nullable=True)      # for FORFEITURE
    violation_reason = Column(Text, nullable=True)             # for FORFEITURE

    # Actors and Audit Timestamps
    requested_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    assigned_officer_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    decided_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    reviewed_at = Column(DateTime, nullable=True)
    decision_reason = Column(Text, nullable=True)

    # Relationships
    deposit = relationship("Deposit", back_populates="approval_requests")
    institution = relationship("Institution")
    contract = relationship("Contract")
    requested_by = relationship("User", foreign_keys=[requested_by_id])
    assigned_officer = relationship("User", foreign_keys=[assigned_officer_id])
    decided_by = relationship("User", foreign_keys=[decided_by_id])
