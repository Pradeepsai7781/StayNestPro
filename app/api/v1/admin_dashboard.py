
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.permissions import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.admin_dashboard import AdminDashboardResponse
from app.services.admin_dashboard_service import get_admin_dashboard

router = APIRouter(
    prefix="/admin-dashboard",
    tags=["Admin Dashboard"],
)

require_admin = require_roles(UserRole.ADMIN)


@router.get(
    "/summary",
    response_model=AdminDashboardResponse,
)
def admin_dashboard_summary(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    hotel_id: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_admin),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before or equal to end_date",
        )

    return get_admin_dashboard(
        db=db,
        start_date=start_date,
        end_date=end_date,
        hotel_id=hotel_id,
        status=status,
    )
