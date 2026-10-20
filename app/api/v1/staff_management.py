from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.security import hash_password
from app.db.session import get_db
from app.models import (
    Hotel,
    StaffActivity,
    StaffAssignment,
    StaffAttendance,
    StaffAttendanceStatus,
    User,
    UserRole,
)
from app.models.audit_log import AuditEventType
from app.services.audit_log_service import record_audit_event


router = APIRouter(prefix="/staff", tags=["Hotel Staff Management"])


# =========================================================
# REQUEST SCHEMAS
# =========================================================

class StaffCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: str
    password: str = Field(min_length=8, max_length=128)
    hotel_id: int


class StaffUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    is_active: bool | None = None


class AttendanceCreate(BaseModel):
    staff_id: int
    hotel_id: int
    attendance_date: date
    status: StaffAttendanceStatus
    notes: str | None = None


class ActivityCreate(BaseModel):
    staff_id: int
    hotel_id: int
    activity: str = Field(min_length=1, max_length=100)
    description: str | None = None


class AssignmentCreate(BaseModel):
    staff_id: int
    hotel_id: int


# =========================================================
# ACCESS-CONTROL HELPERS
# =========================================================

def require_owner_or_admin(user: User) -> None:
    if user.role not in (UserRole.HOTEL_OWNER, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only hotel owners or admins can manage staff.",
        )


def get_managed_hotel(
    db: Session,
    hotel_id: int,
    user: User,
) -> Hotel:
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()

    if hotel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hotel not found.",
        )

    if user.role != UserRole.ADMIN and hotel.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot manage staff for this hotel.",
        )

    return hotel


def get_staff_assignment(
    db: Session,
    staff_id: int,
    hotel_id: int,
) -> StaffAssignment:
    assignment = (
        db.query(StaffAssignment)
        .filter(
            StaffAssignment.staff_id == staff_id,
            StaffAssignment.hotel_id == hotel_id,
        )
        .first()
    )

    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff member is not assigned to this hotel.",
        )

    return assignment


def get_hotel_staff(
    db: Session,
    staff_id: int,
) -> User:
    staff = (
        db.query(User)
        .filter(
            User.id == staff_id,
            User.role == UserRole.HOTEL_STAFF,
        )
        .first()
    )

    if staff is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff account not found.",
        )

    return staff


# =========================================================
# CREATE STAFF ACCOUNT
# POST /api/v1/staff/accounts
# =========================================================

@router.post(
    "/accounts",
    status_code=status.HTTP_201_CREATED,
)
def create_staff(
    payload: StaffCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_owner_or_admin(current_user)
    get_managed_hotel(db, payload.hotel_id, current_user)

    email = payload.email.strip().lower()

    existing = db.query(User).filter(User.email == email).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered.",
        )

    staff = User(
        full_name=payload.full_name.strip(),
        email=email,
        hashed_password=hash_password(payload.password),
        role=UserRole.HOTEL_STAFF,
        is_active=True,
    )

    try:
        db.add(staff)
        db.flush()

        assignment = StaffAssignment(
            staff_id=staff.id,
            hotel_id=payload.hotel_id,
            assigned_by=current_user.id,
        )

        db.add(assignment)

        record_audit_event(
            db=db,
            event_type=AuditEventType.STAFF_ACTIVITY,
            action="STAFF_ACCOUNT_CREATED",
            actor_id=current_user.id,
            description="A hotel staff account was created.",
            entity_type="User",
            entity_id=staff.id,
            details={
                "hotel_id": payload.hotel_id,
                "staff_role": UserRole.HOTEL_STAFF.value,
            },
            commit=False,
        )

        db.commit()
        db.refresh(staff)

    except Exception:
        db.rollback()
        raise

    return {
        "id": staff.id,
        "full_name": staff.full_name,
        "email": staff.email,
        "role": staff.role.value,
        "is_active": staff.is_active,
        "hotel_id": payload.hotel_id,
    }


# =========================================================
# UPDATE STAFF ACCOUNT
# PATCH /api/v1/staff/accounts/{staff_id}
# =========================================================

@router.patch("/accounts/{staff_id}")
def update_staff(
    staff_id: int,
    payload: StaffUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_owner_or_admin(current_user)

    staff = get_hotel_staff(db, staff_id)

    assignments = (
        db.query(StaffAssignment)
        .filter(StaffAssignment.staff_id == staff_id)
        .all()
    )

    if current_user.role != UserRole.ADMIN:
        authorized = False

        for assignment in assignments:
            hotel = (
                db.query(Hotel)
                .filter(Hotel.id == assignment.hotel_id)
                .first()
            )

            if hotel is not None and hotel.owner_id == current_user.id:
                authorized = True
                break

        if not authorized:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized for this staff account.",
            )

    old_full_name = staff.full_name
    old_is_active = staff.is_active

    if payload.full_name is not None:
        staff.full_name = payload.full_name.strip()

    if payload.is_active is not None:
        staff.is_active = payload.is_active

    try:
        record_audit_event(
            db=db,
            event_type=AuditEventType.STAFF_ACTIVITY,
            action="STAFF_ACCOUNT_UPDATED",
            actor_id=current_user.id,
            description="A hotel staff account was updated.",
            entity_type="User",
            entity_id=staff.id,
            details={
                "old_full_name": old_full_name,
                "new_full_name": staff.full_name,
                "old_is_active": old_is_active,
                "new_is_active": staff.is_active,
            },
            commit=False,
        )

        db.commit()
        db.refresh(staff)

    except Exception:
        db.rollback()
        raise

    return {
        "id": staff.id,
        "full_name": staff.full_name,
        "email": staff.email,
        "role": staff.role.value,
        "is_active": staff.is_active,
    }


# =========================================================
# ASSIGN STAFF TO A HOTEL
# POST /api/v1/staff/assignments
# =========================================================

@router.post(
    "/assignments",
    status_code=status.HTTP_201_CREATED,
)
def assign_staff(
    payload: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_owner_or_admin(current_user)
    get_managed_hotel(db, payload.hotel_id, current_user)

    staff = (
        db.query(User)
        .filter(
            User.id == payload.staff_id,
            User.role == UserRole.HOTEL_STAFF,
            User.is_active.is_(True),
        )
        .first()
    )

    if staff is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active hotel staff account not found.",
        )

    existing = (
        db.query(StaffAssignment)
        .filter(
            StaffAssignment.staff_id == payload.staff_id,
            StaffAssignment.hotel_id == payload.hotel_id,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Staff is already assigned to this hotel.",
        )

    assignment = StaffAssignment(
        staff_id=payload.staff_id,
        hotel_id=payload.hotel_id,
        assigned_by=current_user.id,
    )

    try:
        db.add(assignment)
        db.flush()

        record_audit_event(
            db=db,
            event_type=AuditEventType.STAFF_ACTIVITY,
            action="STAFF_ASSIGNED_TO_HOTEL",
            actor_id=current_user.id,
            description="A staff member was assigned to a hotel.",
            entity_type="StaffAssignment",
            entity_id=assignment.id,
            details={
                "staff_id": payload.staff_id,
                "hotel_id": payload.hotel_id,
            },
            commit=False,
        )

        db.commit()
        db.refresh(assignment)

    except Exception:
        db.rollback()
        raise

    return {
        "id": assignment.id,
        "staff_id": assignment.staff_id,
        "hotel_id": assignment.hotel_id,
    }


# =========================================================
# LIST STAFF FOR A HOTEL
# GET /api/v1/staff/hotels/{hotel_id}
# =========================================================

@router.get("/hotels/{hotel_id}")
def list_hotel_staff(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_owner_or_admin(current_user)
    get_managed_hotel(db, hotel_id, current_user)

    assignments = (
        db.query(StaffAssignment)
        .filter(StaffAssignment.hotel_id == hotel_id)
        .all()
    )

    results = []

    for assignment in assignments:
        staff = (
            db.query(User)
            .filter(
                User.id == assignment.staff_id,
                User.role == UserRole.HOTEL_STAFF,
            )
            .first()
        )

        if staff is not None:
            results.append(
                {
                    "id": staff.id,
                    "full_name": staff.full_name,
                    "email": staff.email,
                    "role": staff.role.value,
                    "is_active": staff.is_active,
                    "hotel_id": hotel_id,
                }
            )

    return results


# =========================================================
# RECORD STAFF ATTENDANCE
# POST /api/v1/staff/attendance
# =========================================================

@router.post(
    "/attendance",
    status_code=status.HTTP_201_CREATED,
)
def record_attendance(
    payload: AttendanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_owner_or_admin(current_user)

    get_managed_hotel(db, payload.hotel_id, current_user)

    staff = get_hotel_staff(db, payload.staff_id)

    get_staff_assignment(
        db=db,
        staff_id=staff.id,
        hotel_id=payload.hotel_id,
    )

    attendance_datetime = datetime.combine(
        payload.attendance_date,
        time.min,
        tzinfo=timezone.utc,
    )

    existing = (
        db.query(StaffAttendance)
        .filter(
            StaffAttendance.staff_id == payload.staff_id,
            StaffAttendance.hotel_id == payload.hotel_id,
            StaffAttendance.attendance_date == attendance_datetime,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attendance is already recorded for this hotel and date.",
        )

    record = StaffAttendance(
        staff_id=payload.staff_id,
        hotel_id=payload.hotel_id,
        attendance_date=attendance_datetime,
        status=payload.status,
        notes=payload.notes,
        recorded_by=current_user.id,
    )

    try:
        db.add(record)
        db.flush()

        record_audit_event(
            db=db,
            event_type=AuditEventType.STAFF_ACTIVITY,
            action="STAFF_ATTENDANCE_RECORDED",
            actor_id=current_user.id,
            description="Staff attendance was recorded.",
            entity_type="StaffAttendance",
            entity_id=record.id,
            details={
                "staff_id": payload.staff_id,
                "hotel_id": payload.hotel_id,
                "attendance_date": payload.attendance_date.isoformat(),
                "attendance_status": payload.status.value,
            },
            commit=False,
        )

        db.commit()
        db.refresh(record)

    except Exception:
        db.rollback()
        raise

    return {
        "id": record.id,
        "staff_id": record.staff_id,
        "hotel_id": record.hotel_id,
        "attendance_date": payload.attendance_date,
        "status": record.status.value,
        "notes": record.notes,
    }


# =========================================================
# GET STAFF ATTENDANCE
# GET /api/v1/staff/attendance/{staff_id}
# =========================================================

@router.get("/attendance/{staff_id}")
def get_staff_attendance(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    staff = get_hotel_staff(db, staff_id)

    assignments = (
        db.query(StaffAssignment)
        .filter(StaffAssignment.staff_id == staff_id)
        .all()
    )

    if current_user.role == UserRole.ADMIN:
        authorized_hotel_ids = {
            assignment.hotel_id for assignment in assignments
        }

    elif current_user.role == UserRole.HOTEL_OWNER:
        authorized_hotel_ids = set()

        for assignment in assignments:
            hotel = (
                db.query(Hotel)
                .filter(Hotel.id == assignment.hotel_id)
                .first()
            )

            if hotel is not None and hotel.owner_id == current_user.id:
                authorized_hotel_ids.add(assignment.hotel_id)

    elif current_user.id == staff.id:
        authorized_hotel_ids = {
            assignment.hotel_id for assignment in assignments
        }

    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view attendance.",
        )

    if not authorized_hotel_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No authorized hotel assignment.",
        )

    records = (
        db.query(StaffAttendance)
        .filter(
            StaffAttendance.staff_id == staff_id,
            StaffAttendance.hotel_id.in_(authorized_hotel_ids),
        )
        .all()
    )

    return [
        {
            "id": record.id,
            "staff_id": record.staff_id,
            "hotel_id": record.hotel_id,
            "attendance_date": record.attendance_date,
            "status": record.status.value,
            "notes": record.notes,
        }
        for record in records
    ]


# =========================================================
# RECORD STAFF ACTIVITY
# POST /api/v1/staff/activities
# =========================================================

@router.post(
    "/activities",
    status_code=status.HTTP_201_CREATED,
)
def record_staff_activity(
    payload: ActivityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_owner_or_admin(current_user)

    get_managed_hotel(db, payload.hotel_id, current_user)

    staff = get_hotel_staff(db, payload.staff_id)

    get_staff_assignment(
        db=db,
        staff_id=staff.id,
        hotel_id=payload.hotel_id,
    )

    activity_name = payload.activity.strip()

    if not activity_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Activity cannot be empty.",
        )

    activity = StaffActivity(
        staff_id=payload.staff_id,
        hotel_id=payload.hotel_id,
        activity=activity_name,
        description=payload.description,
        recorded_by=current_user.id,
    )

    try:
        db.add(activity)
        db.flush()

        record_audit_event(
            db=db,
            event_type=AuditEventType.STAFF_ACTIVITY,
            action="STAFF_ACTIVITY_RECORDED",
            actor_id=current_user.id,
            description="A staff activity was recorded.",
            entity_type="StaffActivity",
            entity_id=activity.id,
            details={
                "staff_id": payload.staff_id,
                "hotel_id": payload.hotel_id,
                "activity": activity_name,
            },
            commit=False,
        )

        db.commit()
        db.refresh(activity)

    except Exception:
        db.rollback()
        raise

    return {
        "id": activity.id,
        "staff_id": activity.staff_id,
        "hotel_id": activity.hotel_id,
        "activity": activity.activity,
        "description": activity.description,
        "created_at": activity.created_at,
    }