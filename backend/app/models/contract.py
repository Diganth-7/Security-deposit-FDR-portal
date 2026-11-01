import enum
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, Numeric, Date, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.database import Base
from backend.app.utils.clock import utc_now

class ContractStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    TERMINATED = "TERMINATED"

class Contract(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    contract_number = Column(String(100), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Institution owning this contract
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    contract_type = Column(String(100), nullable=False, default="Institutional Affiliation")
    contract_amount = Column(Numeric(15, 2), nullable=False, default=0.0)
    required_deposit_amount = Column(Numeric(15, 2), nullable=False, default=0.0)
    
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    
    status = Column(Enum(ContractStatus), default=ContractStatus.DRAFT, nullable=False, index=True)
    
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    institution = relationship("Institution", back_populates="contracts")
    deposits = relationship("Deposit", back_populates="contract")
    documents = relationship("Document", back_populates="contract")
