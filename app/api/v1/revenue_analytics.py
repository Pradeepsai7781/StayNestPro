
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.revenue_analytics import (
    RevenueBreakdown,
)
from app.services.revenue_analytics_service import (
    get_daily_revenue,
    get_monthly_revenue,
)

router = APIRouter(
    prefix="/revenue-analytics",
    tags=["Hotel Revenue Analytics"],
)


def require_admin(current_user: User):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only administrators can view revenue analytics.",
        )


@router.get("/daily", response_model=list[RevenueBreakdown])
def daily_revenue(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    if start_date > end_date:
        raise HTTPException(
            status_code=422,
            detail="start_date must be on or before end_date.",
        )

    if (end_date - start_date).days > 365:
        raise HTTPException(
            status_code=422,
            detail="The daily date range cannot exceed 366 days.",
        )

    return get_daily_revenue(db, start_date, end_date)


@router.get("/monthly", response_model=RevenueBreakdown)
def monthly_revenue(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    return get_monthly_revenue(db, year, month)
