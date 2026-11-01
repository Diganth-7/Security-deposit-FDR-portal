from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Actor who performed the action (None if system automated job)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Action type
    action = Column(String(100), nullable=False, index=True)
    
    # Target FDR
    deposit_id = Column(Integer, ForeignKey("deposits.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Description or structured payload
    details = Column(Text, nullable=True)
    
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    actor = relationship("User", foreign_keys=[actor_id])
    deposit = relationship("Deposit", back_populates="audit_logs")
