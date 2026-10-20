
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.hotel_owner_dashboard import HotelOwnerDashboardResponse
from app.services.hotel_owner_dashboard_service import (
    get_hotel_owner_dashboard,
)


router = APIRouter(
    prefix="/hotel-owner-dashboard",
    tags=["Hotel Owner Dashboard"],
)


@router.get(
    "/summary",
    response_model=HotelOwnerDashboardResponse,
)
def get_dashboard_summary(
    dashboard_date: date | None = Query(
        default=None,
        description="Dashboard date in YYYY-MM-DD format; defaults to today.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return dashboard analytics for the authenticated hotel owner."""

    if current_user.role != UserRole.HOTEL_OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only hotel owners can access this dashboard.",
        )

    return get_hotel_owner_dashboard(
        db=db,
        owner_id=current_user.id,
        dashboard_date=dashboard_date,
    )

