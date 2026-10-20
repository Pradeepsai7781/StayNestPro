
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.db.session import get_db
from app.models import Notification, User, UserRole

router = APIRouter(prefix="/notifications", tags=["In-App Notifications"])

require_customer = require_roles(UserRole.CUSTOMER)


@router.get("")
def list_notifications(
    unread_only: bool = False,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    query = db.query(Notification).filter(
        Notification.user_id == current_user.id
    )

    if unread_only:
        query = query.filter(Notification.is_read.is_(False))

    items = query.order_by(Notification.created_at.desc()).all()

    return {
        "count": len(items),
        "unread_count": db.query(Notification).filter(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        ).count(),
        "notifications": [
            {
                "id": item.id,
                "title": item.title,
                "message": item.message,
                "notification_type": item.notification_type,
                "is_read": item.is_read,
                "related_reservation_id": item.related_reservation_id,
                "created_at": item.created_at,
                "read_at": item.read_at,
            }
            for item in items
        ],
    }


@router.patch("/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    ).first()

    if notification is None:
        raise HTTPException(
            status_code=404,
            detail="Notification not found.",
        )

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)

    return {
        "message": "Notification marked as read.",
        "id": notification.id,
        "is_read": notification.is_read,
    }


@router.patch("/read-all")
def mark_all_notifications_read(
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    items = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read.is_(False),
    ).all()

    now = datetime.now(timezone.utc)

    for item in items:
        item.is_read = True
        item.read_at = now

    db.commit()

    return {
        "message": "All notifications marked as read.",
        "updated_count": len(items),
    }
