
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.db.session import get_db
from app.models import Hotel, HotelStatus, User, UserRole
from app.models.audit_log import AuditEventType
from app.services.audit_log_service import record_audit_event
from app.schemas.admin import (
    AdminUserResponse,
    HotelDecisionRequest,
    UserRoleUpdate,
    UserStatusUpdate,
)
from app.schemas.hotel import HotelResponse

router = APIRouter(prefix="/admin", tags=["Admin"])
require_admin = require_roles(UserRole.ADMIN)


def ensure_another_active_admin_exists(
    db: Session,
    target_user: User,
) -> None:
    """Prevent removing the last active administrator."""
    if target_user.role != UserRole.ADMIN or not target_user.is_active:
        return

    other_active_admins = (
        db.query(User)
        .filter(
            User.role == UserRole.ADMIN,
            User.is_active.is_(True),
            User.id != target_user.id,
        )
        .count()
    )

    if other_active_admins == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove or deactivate the last active admin",
        )


def get_hotel_or_404(hotel_id: int, db: Session) -> Hotel:
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()
    if hotel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hotel not found",
        )
    return hotel


@router.get("/users", response_model=list[AdminUserResponse])
def list_users(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.query(User).order_by(User.id).all()


@router.patch("/users/{user_id}/role", response_model=AdminUserResponse)
def update_user_role(
    user_id: int,
    request: UserRoleUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if request.role != UserRole.ADMIN:
        ensure_another_active_admin_exists(db, user)

    old_role = user.role
    user.role = request.role

    try:
        record_audit_event(
            db=db,
            event_type=AuditEventType.ADMIN_ACTION,
            action="USER_ROLE_UPDATED",
            actor_id=current_user.id,
            description="An administrator changed a user's role.",
            entity_type="User",
            entity_id=user.id,
            details={
                "old_role": old_role.value,
                "new_role": user.role.value,
            },
            commit=False,
        )
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise

    return user


@router.patch("/users/{user_id}/status", response_model=AdminUserResponse)
def update_user_status(
    user_id: int,
    request: UserStatusUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if user_id == current_user.id and not request.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if not request.is_active:
        ensure_another_active_admin_exists(db, user)

    old_status = user.is_active
    user.is_active = request.is_active

    try:
        record_audit_event(
            db=db,
            event_type=AuditEventType.ADMIN_ACTION,
            action="USER_STATUS_UPDATED",
            actor_id=current_user.id,
            description="An administrator changed a user's active status.",
            entity_type="User",
            entity_id=user.id,
            details={
                "old_is_active": old_status,
                "new_is_active": user.is_active,
            },
            commit=False,
        )
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise

    return user


@router.get("/hotels/pending", response_model=list[HotelResponse])
def list_pending_hotels(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return (
        db.query(Hotel)
        .filter(Hotel.status == HotelStatus.PENDING)
        .order_by(Hotel.id)
        .all()
    )


@router.patch("/hotels/{hotel_id}/decision", response_model=HotelResponse)
def decide_hotel_application(
    hotel_id: int,
    request: HotelDecisionRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    hotel = get_hotel_or_404(hotel_id, db)

    if hotel.status != HotelStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending hotel applications can be approved or rejected",
        )

    old_status = hotel.status
    hotel.status = HotelStatus(request.decision)

    try:
        record_audit_event(
            db=db,
            event_type=AuditEventType.ADMIN_ACTION,
            action="HOTEL_APPLICATION_DECIDED",
            actor_id=current_user.id,
            description="An administrator approved or rejected a hotel application.",
            entity_type="Hotel",
            entity_id=hotel.id,
            details={
                "old_status": old_status.value,
                "new_status": hotel.status.value,
            },
            commit=False,
        )
        db.commit()
        db.refresh(hotel)
    except Exception:
        db.rollback()
        raise

    return hotel


@router.patch("/hotels/{hotel_id}/suspend", response_model=HotelResponse)
def suspend_hotel(
    hotel_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    hotel = get_hotel_or_404(hotel_id, db)

    if hotel.status != HotelStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only approved hotels can be suspended",
        )

    old_status = hotel.status
    hotel.status = HotelStatus.SUSPENDED

    try:
        record_audit_event(
            db=db,
            event_type=AuditEventType.ADMIN_ACTION,
            action="HOTEL_SUSPENDED",
            actor_id=current_user.id,
            description="An administrator suspended a hotel.",
            entity_type="Hotel",
            entity_id=hotel.id,
            details={
                "old_status": old_status.value,
                "new_status": hotel.status.value,
            },
            commit=False,
        )
        db.commit()
        db.refresh(hotel)
    except Exception:
        db.rollback()
        raise

    return hotel


@router.patch("/hotels/{hotel_id}/reactivate", response_model=HotelResponse)
def reactivate_hotel(
    hotel_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    hotel = get_hotel_or_404(hotel_id, db)

    if hotel.status != HotelStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only suspended hotels can be reactivated",
        )

    old_status = hotel.status
    hotel.status = HotelStatus.APPROVED

    try:
        record_audit_event(
            db=db,
            event_type=AuditEventType.ADMIN_ACTION,
            action="HOTEL_REACTIVATED",
            actor_id=current_user.id,
            description="An administrator reactivated a hotel.",
            entity_type="Hotel",
            entity_id=hotel.id,
            details={
                "old_status": old_status.value,
                "new_status": hotel.status.value,
            },
            commit=False,
        )
        db.commit()
        db.refresh(hotel)
    except Exception:
        db.rollback()
        raise

    return hotel
