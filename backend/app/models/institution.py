from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from backend.app.database import Base

class Institution(Base):
    __tablename__ = "institutions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    aicte_id = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(255), index=True, nullable=False)
    state = Column(String(100), nullable=False)
    city = Column(String(100), nullable=False)
    address = Column(String(500), nullable=True)
    institute_type = Column(String(100), default="Technical Institute", nullable=False)
    contact_email = Column(String(255), nullable=False)
    contact_phone = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    users = relationship("User", back_populates="institution")
    deposits = relationship("Deposit", back_populates="institution", cascade="all, delete-orphan")
    contracts = relationship("Contract", back_populates="institution", cascade="all, delete-orphan")

