from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.occupancy_analytics import (
    DailyOccupancySummary,
    OccupancySummary,
)
from app.services.occupancy_analytics_service import get_occupancy_summary


router = APIRouter(
    prefix="/occupancy-analytics",
    tags=["Hotel Occupancy Analytics"],
)


def require_admin(current_user: User) -> None:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only administrators can access occupancy analytics.",
        )


@router.get(
    "/summary",
    response_model=OccupancySummary,
)
def occupancy_summary(
    start_date: date = Query(...),
    end_date: date = Query(...),
    hotel_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    if start_date > end_date:
        raise HTTPException(
            status_code=422,
            detail="start_date cannot be after end_date.",
        )

    if (end_date - start_date).days > 365:
        raise HTTPException(
            status_code=422,
            detail="The requested date range cannot exceed 366 days.",
        )

    return get_occupancy_summary(
        db=db,
        start_date=start_date,
        end_date=end_date,
        hotel_id=hotel_id,
    )


@router.get(
    "/daily",
    response_model=list[DailyOccupancySummary],
)
def daily_occupancy(
    start_date: date = Query(...),
    end_date: date = Query(...),
    hotel_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    if start_date > end_date:
        raise HTTPException(
            status_code=422,
            detail="start_date cannot be after end_date.",
        )

    if (end_date - start_date).days > 365:
        raise HTTPException(
            status_code=422,
            detail="The requested date range cannot exceed 366 days.",
        )

    summary = get_occupancy_summary(
        db=db,
        start_date=start_date,
        end_date=end_date,
        hotel_id=hotel_id,
    )

    return summary["daily_summaries"]