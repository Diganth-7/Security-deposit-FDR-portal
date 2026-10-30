from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

class InstitutionBase(BaseModel):
    aicte_id: str = Field(..., min_length=3, max_length=50, description="Unique AICTE approval ID e.g. 1-3329182741")
    name: str = Field(..., min_length=3, max_length=255)
    state: str = Field(..., min_length=2, max_length=100)
    city: str = Field(..., min_length=2, max_length=100)
    address: Optional[str] = None
    institute_type: str = "Technical Institute"
    contact_email: EmailStr
    contact_phone: Optional[str] = None

class InstitutionCreate(InstitutionBase):
    pass

class InstitutionResponse(InstitutionBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
