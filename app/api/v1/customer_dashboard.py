
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.permissions import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.customer_dashboard import CustomerDashboardResponse
from app.services.customer_dashboard_service import (
    get_customer_dashboard,
)

router = APIRouter(
    prefix="/customer-dashboard",
    tags=["Customer Dashboard"],
)

require_customer = require_roles(UserRole.CUSTOMER)


@router.get(
    "/summary",
    response_model=CustomerDashboardResponse,
)
def customer_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_customer),
):
    return get_customer_dashboard(
        db=db,
        user_id=current_user.id,
    )
