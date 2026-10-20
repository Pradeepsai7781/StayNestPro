
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models import User, UserRole
from app.schemas.customer_analytics import CustomerAnalyticsResponse
from app.services.customer_analytics_service import get_customer_analytics


router = APIRouter(
    prefix="/customer-analytics",
    tags=["Customer Analytics"],
)


@router.get(
    "/summary",
    response_model=CustomerAnalyticsResponse,
)
def customer_analytics_summary(
    start_date: date = Query(
        ...,
        description="Start date (YYYY-MM-DD)",
    ),
    end_date: date = Query(
        ...,
        description="End date (YYYY-MM-DD)",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return customer booking, spending, destination, and retention analytics."""

    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can access customer analytics.",
        )

    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be on or before end_date.",
        )

    try:
        return get_customer_analytics(
            db=db,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
