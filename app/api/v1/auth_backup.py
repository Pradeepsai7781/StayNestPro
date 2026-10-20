
from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.security import hash_password
from app.db.session import get_db
from app.models import Hotel, User, UserRole
from app.models.staff_management import (
    StaffActivity,
    StaffAssignment,
    StaffAttendance,
    StaffAttendanceStatus,
)

router = APIRouter(prefix="/staff", tags=["Hotel Staff Management"])


class StaffCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    hotel_id: int


class StaffUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    is_active: bool | None = None


class AttendanceCreate(BaseModel):
    staff_id: int
    attendance_date: date
    status: StaffAttendanceStatus = StaffAttendanceStatus.PRESENT
    notes: str | None = None


class ActivityCreate(BaseModel):
    staff_id: int
    activity: str = Field(min_length=1, max_length=100)
    description: str | None = None


class AssignmentCreate(BaseModel):
    staff_id: int
    hotel_id: int


def require_manager(user: User) -> None:
    if user.role not in (UserRole.HOTEL_OWNER, UserRole.ADMIN):
        raise HTTPException(
            status_code=403,
            detail="Only hotel owners or admins can manage staff.",
        )


def get_managed_hotel(db: Session, hotel_id: int, user: User) -> Hotel:
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()

    if hotel is None:
        raise HTTPException(status_code=404, detail="Hotel not found.")

    if user.role != UserRole.ADMIN and hotel.owner_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="You cannot manage staff for this hotel.",
        )

    return hotel


def get_hotel_staff(db: Session, staff_id: int, hotel_id: int) -> User:
    staff = db.query(User).filter(
        User.id == staff_id,
        User.role == UserRole.HOTEL_STAFF,
    ).first()

    if staff is None:
        raise HTTPException(status_code=404, detail="Hotel staff not found.")

    assignment = db.query(StaffAssignment.id).filter(
        StaffAssignment.staff_id == staff_id,
        StaffAssignment.hotel_id == hotel_id,
    ).first()

    if assignment is None:
        raise HTTPException(
            status_code=403,
            detail="Staff member is not assigned to this hotel.",
        )

    return staff


@router.post("/accounts", status_code=status.HTTP_201_CREATED)
def create_staff(
    payload: StaffCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_manager(current_user)
    hotel = get_managed_hotel(db, payload.hotel_id, current_user)

    email = str(payload.email).lower()

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email is already registered.")

    staff = User(
        full_name=payload.full_name.strip(),
        email=email,
        hashed_password=hash_password(payload.password),
        role=UserRole.HOTEL_STAFF,
        is_active=True,
    )

    db.add(staff)
    db.flush()

    db.add(
        StaffAssignment(
            staff_id=staff.id,
            hotel_id=hotel.id,
            assigned_by=current_user.id,
        )
    )

    db.add(
        StaffActivity(
            staff_id=staff.id,
            hotel_id=hotel.id,
            activity="STAFF_ACCOUNT_CREATED",
            description="Staff account created.",
            recorded_by=current_user.id,
        )
    )

    db.commit()
    db.refresh(staff)

    return {
        "id": staff.id,
        "full_name": staff.full_name,
        "email": staff.email,
        "role": staff.role.value,
        "is_active": staff.is_active,
        "hotel_id": hotel.id,
    }


@router.get("/accounts")
def list_staff(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_manager(current_user)
    get_managed_hotel(db, hotel_id, current_user)

    assignments = db.query(StaffAssignment).filter(
        StaffAssignment.hotel_id == hotel_id
    ).all()

    staff_ids = [assignment.staff_id for assignment in assignments]

    if not staff_ids:
        return []

    staff_members = db.query(User).filter(
        User.id.in_(staff_ids),
        User.role == UserRole.HOTEL_STAFF,
    ).all()

    return [
        {
            "id": staff.id,
            "full_name": staff.full_name,
            "email": staff.email,
            "role": staff.role.value,
            "is_active": staff.is_active,
        }
        for staff in staff_members
    ]


@router.patch("/accounts/{staff_id}")
def update_staff(
    staff_id: int,
    hotel_id: int,
    payload: StaffUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_manager(current_user)
    hotel = get_managed_hotel(db, hotel_id, current_user)
    staff = get_hotel_staff(db, staff_id, hotel.id)

    if payload.full_name is not None:
        staff.full_name = payload.full_name.strip()

    if payload.is_active is not None:
        staff.is_active = payload.is_active

    db.add(
        StaffActivity(
            staff_id=staff.id,
            hotel_id=hotel.id,
            activity="STAFF_ACCOUNT_UPDATED",
            description="Staff account updated.",
            recorded_by=current_user.id,
        )
    )

    db.commit()
    db.refresh(staff)

    return {
        "id": staff.id,
        "full_name": staff.full_name,
        "email": staff.email,
        "role": staff.role.value,
        "is_active": staff.is_active,
        "hotel_id": hotel.id,
    }


@router.post("/assignments", status_code=status.HTTP_201_CREATED)
def assign_staff(
    payload: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_manager(current_user)
    get_managed_hotel(db, payload.hotel_id, current_user)

    staff = db.query(User).filter(
        User.id == payload.staff_id,
        User.role == UserRole.HOTEL_STAFF,
    ).first()

    if staff is None:
        raise HTTPException(status_code=404, detail="Hotel staff not found.")

    existing = db.query(StaffAssignment).filter(
        StaffAssignment.staff_id == payload.staff_id,
        StaffAssignment.hotel_id == payload.hotel_id,
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Staff member is already assigned to this hotel.",
        )

    assignment = StaffAssignment(
        staff_id=staff.id,
        hotel_id=payload.hotel_id,
        assigned_by=current_user.id,
    )

    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    return {
        "id": assignment.id,
        "staff_id": assignment.staff_id,
        "hotel_id": assignment.hotel_id,
    }


@router.post("/attendance", status_code=status.HTTP_201_CREATED)
def record_attendance(
    hotel_id: int,
    payload: AttendanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_manager(current_user)
    get_managed_hotel(db, hotel_id, current_user)
    staff = get_hotel_staff(db, payload.staff_id, hotel_id)

    attendance_datetime = datetime.combine(
        payload.attendance_date,
        time.min,
        tzinfo=timezone.utc,
    )

    existing = db.query(StaffAttendance).filter(
        StaffAttendance.staff_id == staff.id,
        StaffAttendance.hotel_id == hotel_id,
        StaffAttendance.attendance_date == attendance_datetime,
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Attendance already exists for this staff member and date.",
        )

    attendance = StaffAttendance(
        staff_id=staff.id,
        hotel_id=hotel_id,
        attendance_date=attendance_datetime,
        status=payload.status,
        notes=payload.notes,
        recorded_by=current_user.id,
    )

    db.add(attendance)
    db.add(
        StaffActivity(
            staff_id=staff.id,
            hotel_id=hotel_id,
            activity="ATTENDANCE_RECORDED",
            description=f"Attendance marked {payload.status.value}.",
            recorded_by=current_user.id,
        )
    )

    db.commit()
    db.refresh(attendance)
    return attendance


@router.get("/attendance/{staff_id}")
def get_staff_attendance(
    staff_id: int,
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_manager(current_user)
    get_managed_hotel(db, hotel_id, current_user)
    get_hotel_staff(db, staff_id, hotel_id)

    return db.query(StaffAttendance).filter(
        StaffAttendance.staff_id == staff_id,
        StaffAttendance.hotel_id == hotel_id,
    ).order_by(StaffAttendance.attendance_date.desc()).all()


@router.post("/activities", status_code=status.HTTP_201_CREATED)
def record_activity(
    hotel_id: int,
    payload: ActivityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_manager(current_user)
    get_managed_hotel(db, hotel_id, current_user)
    staff = get_hotel_staff(db, payload.staff_id, hotel_id)

    activity = StaffActivity(
        staff_id=staff.id,
        hotel_id=hotel_id,
        activity=payload.activity,
        description=payload.description,
        recorded_by=current_user.id,
    )

    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity
