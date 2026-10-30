import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.database import Base

class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    INSTITUTION = "INSTITUTION"
    OFFICER = "OFFICER"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.INSTITUTION, nullable=False)
    
    # Optional foreign key linking user to their institution (for INSTITUTION role)
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True)
    
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    institution = relationship("Institution", back_populates="users", foreign_keys=[institution_id])
    submitted_deposits = relationship("Deposit", back_populates="submitted_by", foreign_keys="Deposit.submitted_by_id")
    verified_deposits = relationship("Deposit", back_populates="verified_by", foreign_keys="Deposit.verified_by_id")
