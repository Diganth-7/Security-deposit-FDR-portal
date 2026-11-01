import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.database import Base

class DocumentType(str, enum.Enum):
    FDR_CERTIFICATE = "FDR_CERTIFICATE"
    BANK_RECEIPT = "BANK_RECEIPT"
    CONTRACT_DOCUMENT = "CONTRACT_DOCUMENT"
    RENEWAL_DOCUMENT = "RENEWAL_DOCUMENT"
    RELEASE_DOCUMENT = "RELEASE_DOCUMENT"
    OTHER = "OTHER"

class DocumentVerificationStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Associated FDR Deposit (Required)
    deposit_id = Column(Integer, ForeignKey("deposits.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Associated Institution (Required)
    institution_id = Column(Integer, ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Optional linked Contract
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Filenames
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False, unique=True, index=True)
    
    # File Metadata
    document_type = Column(Enum(DocumentType), default=DocumentType.FDR_CERTIFICATE, nullable=False, index=True)
    file_size = Column(Integer, nullable=False)  # in bytes
    mime_type = Column(String(100), nullable=False)
    
    # Upload Audit
    upload_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    uploaded_by_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    # Verification Audit
    verification_status = Column(Enum(DocumentVerificationStatus), default=DocumentVerificationStatus.PENDING, nullable=False, index=True)
    verified_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    verification_timestamp = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Relationships
    deposit = relationship("Deposit", back_populates="documents")
    institution = relationship("Institution")
    contract = relationship("Contract", back_populates="documents")
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_id])
    verified_by = relationship("User", foreign_keys=[verified_by_id])
