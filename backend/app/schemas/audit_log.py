from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class AuditLogResponse(BaseModel):
    id: int
    actor_id: Optional[int] = None
    action: str
    deposit_id: int
    details: Optional[str] = None
    timestamp: datetime

    model_config = {"from_attributes": True}
