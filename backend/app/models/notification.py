from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from backend.app.database import Base
from backend.app.models.user import UserRole

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Recipient user if directed to specific individual
    recipient_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Recipient role for broad officer/admin broadcast
    recipient_role = Column(Enum(UserRole), nullable=True, index=True)
    
    # Associated institution
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Target FDR
    deposit_id = Column(Integer, ForeignKey("deposits.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Reminder category (REMINDER_30_DAYS, REMINDER_7_DAYS, REMINDER_1_DAY, REMINDER_ON_MATURITY, etc.)
    reminder_type = Column(String(100), nullable=False, index=True)
    
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    days_remaining = Column(Integer, nullable=True)
    
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    recipient_user = relationship("User", foreign_keys=[recipient_user_id])
    institution = relationship("Institution")
    deposit = relationship("Deposit", back_populates="notifications")
