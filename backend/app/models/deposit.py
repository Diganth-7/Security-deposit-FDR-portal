import enum
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.database import Base

class DepositStatus(str, enum.Enum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFIED = "VERIFIED"
    ACTIVE = "ACTIVE"
    MATURED = "MATURED"
    RELEASED = "RELEASED"
    REJECTED = "REJECTED"

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
    
    # Institution that owns this deposit
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    
    # User who submitted the FDR
    submitted_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    
    # Officer who verified / inspected the FDR
    verified_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verification_remarks = Column(Text, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    institution = relationship("Institution", back_populates="deposits")
    submitted_by = relationship("User", foreign_keys=[submitted_by_id], back_populates="submitted_deposits")
    verified_by = relationship("User", foreign_keys=[verified_by_id], back_populates="verified_deposits")
