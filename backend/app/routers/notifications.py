from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models.notification import Notification
from backend.app.models.user import User, UserRole
from backend.app.schemas.notification import NotificationResponse, NotificationUnreadCount
from backend.app.auth.dependencies import get_current_user
from backend.app.utils.clock import utc_now

router = APIRouter(prefix="/notifications", tags=["In-App Reminders & Notifications"])

def get_user_notification_filter(query, current_user: User):
    """
    Applies role and institution scoping for notification visibility.
    - INSTITUTION users see notifications for their institution or direct user ID.
    - OFFICER / ADMIN users see notifications addressed to them or to their role.
    """
    if current_user.role == UserRole.INSTITUTION:
        if not current_user.institution_id:
            return query.filter(Notification.recipient_user_id == current_user.id)
        return query.filter(
            (Notification.recipient_user_id == current_user.id) |
            (
                (Notification.institution_id == current_user.institution_id) &
                (Notification.recipient_user_id.is_(None))
            )
        )
    else:
        # Officer / Admin
        return query.filter(
            (Notification.recipient_user_id == current_user.id) |
            (Notification.recipient_role.in_([UserRole.OFFICER, UserRole.ADMIN]))
        )

@router.get("", response_model=List[NotificationResponse])
def get_notifications(
    unread_only: bool = Query(False, description="Filter for unread notifications only"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists in-app maturity reminders and workflow notifications for the authenticated user.
    """
    query = db.query(Notification)
    query = get_user_notification_filter(query, current_user)

    if unread_only:
        query = query.filter(Notification.is_read == False)

    return query.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()

@router.get("/unread-count", response_model=NotificationUnreadCount)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the total count of unread notifications for badge counters.
    """
    query = db.query(Notification).filter(Notification.is_read == False)
    query = get_user_notification_filter(query, current_user)
    count = query.count()
    return {"unread_count": count}

@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Marks a specific notification as read.
    Enforces access control so users can only update their own notifications.
    """
    query = db.query(Notification).filter(Notification.id == notification_id)
    query = get_user_notification_filter(query, current_user)
    notif = query.first()

    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found or access denied."
        )

    notif.is_read = True
    notif.read_at = utc_now()
    db.commit()
    db.refresh(notif)
    return notif
