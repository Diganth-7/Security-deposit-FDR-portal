from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from backend.app.models.user import UserRole

class NotificationBase(BaseModel):
    title: str
    message: str
    reminder_type: str
    days_remaining: Optional[int] = None
    deposit_id: int
    institution_id: Optional[int] = None

class NotificationResponse(NotificationBase):
    id: int
    recipient_user_id: Optional[int] = None
    recipient_role: Optional[UserRole] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}

class NotificationUnreadCount(BaseModel):
    unread_count: int
