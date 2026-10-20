
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import User, UserRole
from app.models.audit_log import AuditEventType, AuditLog
from app.schemas.audit_log import AuditLogListResponse


router = APIRouter(
    prefix="/audit-logs",
    tags=["Audit Logs"],
)


@router.get("", response_model=AuditLogListResponse)
def list_audit_logs(
    event_type: AuditEventType | None = Query(default=None),
    actor_id: int | None = Query(default=None, gt=0),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Allow administrators to read audit logs without modifying them."""

    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only administrators can view audit logs.",
        )

    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=422,
            detail="start_date must be before or equal to end_date.",
        )

    query = db.query(AuditLog)

    if event_type is not None:
        query = query.filter(AuditLog.event_type == event_type)

    if actor_id is not None:
        query = query.filter(AuditLog.actor_id == actor_id)

    if start_date is not None:
        query = query.filter(AuditLog.created_at >= start_date)

    if end_date is not None:
        query = query.filter(AuditLog.created_at <= end_date)

    total = query.count()

    items = (
        query.order_by(
            AuditLog.created_at.desc(),
            AuditLog.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return AuditLogListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
