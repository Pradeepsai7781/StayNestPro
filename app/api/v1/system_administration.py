from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import Hotel, Reservation, User, UserRole
from app.models.financial_management import FinancialRecord, Settlement
from app.models.payment import Payment
from app.models.refund import Refund
from app.models.security_alert import SecurityAlert, SecurityAlertStatus

router = APIRouter(prefix="/system-admin", tags=["Advanced Platform Administration"])


def require_admin(user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only administrators can access system administration.")


@router.get("/overview")
def operational_overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_admin(current_user)
    return {
        "generated_at": datetime.now(timezone.utc),
        "accounts": {
            "total_users": db.query(User).count(),
            "active_users": db.query(User).filter(User.is_active.is_(True)).count(),
            "administrators": db.query(User).filter(User.role == UserRole.ADMIN).count(),
        },
        "hotels": {"total": db.query(Hotel).count()},
        "reservations": {"total": db.query(Reservation).count()},
        "payments": {"total": db.query(Payment).count()},
        "refunds": {"total": db.query(Refund).count()},
        "financial_records": {"total": db.query(FinancialRecord).count()},
        "settlements": {"total": db.query(Settlement).count()},
        "security": {"open_alerts": db.query(SecurityAlert).filter(SecurityAlert.status == SecurityAlertStatus.OPEN).count()},
    }


@router.get("/health")
def system_health(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_admin(current_user)
    database_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db.rollback()
        database_status = "unavailable"
    return {
        "status": "healthy" if database_status == "healthy" else "degraded",
        "database": database_status,
        "checked_at": datetime.now(timezone.utc),
    }
