
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.hotel import Hotel
from app.models.housekeeping import (
    CleaningRequest,
    HousekeepingTask,
    HousekeepingTaskStatus,
    InspectionRecord,
    InspectionResult,
    MaintenanceRequest,
    MaintenanceStatus,
)
from app.models.room import Room, RoomStatus
from app.models.user import User, UserRole

router = APIRouter(prefix="/housekeeping", tags=["Housekeeping Management"])


class RoomStatusUpdate(BaseModel):
    status: RoomStatus


class TaskCreate(BaseModel):
    room_id: int
    assigned_to: int | None = None
    notes: str | None = None


class TaskStatusUpdate(BaseModel):
    status: HousekeepingTaskStatus


class CleaningRequestCreate(BaseModel):
    room_id: int
    description: str = Field(min_length=1)


class InspectionCreate(BaseModel):
    room_id: int
    result: InspectionResult = InspectionResult.PENDING
    notes: str | None = None


class MaintenanceCreate(BaseModel):
    room_id: int
    description: str = Field(min_length=1)
    assigned_to: int | None = None


class MaintenanceUpdate(BaseModel):
    status: MaintenanceStatus


def role_value(user: User) -> str:
    role = user.role
    return role.value if hasattr(role, "value") else str(role)


def ensure_staff_or_admin(user: User) -> None:
    allowed_roles = {
        UserRole.HOTEL_OWNER.value,
        UserRole.HOTEL_STAFF.value,
        UserRole.ADMIN.value,
    }

    if role_value(user) not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only hotel staff, hotel owners, or admins can perform this action.",
        )


def get_authorized_room(db: Session, room_id: int, user: User) -> Room:
    room = db.query(Room).filter(Room.id == room_id).first()

    if room is None:
        raise HTTPException(status_code=404, detail="Room not found.")

    if role_value(user) == UserRole.ADMIN.value:
        return room

    hotel = db.query(Hotel).filter(Hotel.id == room.hotel_id).first()

    if hotel is None or hotel.owner_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to manage this room.",
        )

    return room


def validate_assignee(db: Session, assigned_to: int | None) -> None:
    if assigned_to is None:
        return

    staff = (
        db.query(User)
        .filter(
            User.id == assigned_to,
            User.role == UserRole.HOTEL_STAFF,
            User.is_active.is_(True),
        )
        .first()
    )

    if staff is None:
        raise HTTPException(
            status_code=400,
            detail="assigned_to must be an active hotel staff user.",
        )


@router.patch("/rooms/{room_id}/status")
def update_room_status(
    room_id: int,
    payload: RoomStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_staff_or_admin(current_user)
    room = get_authorized_room(db, room_id, current_user)

    room.status = payload.status
    db.commit()
    db.refresh(room)

    return {"room_id": room.id, "status": room.status.value}


@router.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_staff_or_admin(current_user)
    get_authorized_room(db, payload.room_id, current_user)
    validate_assignee(db, payload.assigned_to)

    task = HousekeepingTask(
        room_id=payload.room_id,
        assigned_to=payload.assigned_to,
        created_by=current_user.id,
        notes=payload.notes,
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    return task


@router.patch("/tasks/{task_id}/status")
def update_task_status(
    task_id: int,
    payload: TaskStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_staff_or_admin(current_user)

    task = (
        db.query(HousekeepingTask)
        .filter(HousekeepingTask.id == task_id)
        .first()
    )

    if task is None:
        raise HTTPException(status_code=404, detail="Housekeeping task not found.")

    if role_value(current_user) == UserRole.HOTEL_STAFF.value:
        if task.assigned_to != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Staff can update only tasks assigned to them.",
            )

        if db.query(Room).filter(Room.id == task.room_id).first() is None:
            raise HTTPException(status_code=404, detail="Room not found.")
    else:
        get_authorized_room(db, task.room_id, current_user)

    task.status = payload.status
    task.completed_at = (
        datetime.now(timezone.utc)
        if payload.status == HousekeepingTaskStatus.COMPLETED
        else None
    )

    db.commit()
    db.refresh(task)

    return task


@router.post("/cleaning-requests", status_code=status.HTTP_201_CREATED)
def create_cleaning_request(
    payload: CleaningRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_staff_or_admin(current_user)
    get_authorized_room(db, payload.room_id, current_user)

    cleaning_request = CleaningRequest(
        room_id=payload.room_id,
        requested_by=current_user.id,
        description=payload.description.strip(),
    )

    db.add(cleaning_request)
    db.commit()
    db.refresh(cleaning_request)

    return cleaning_request


@router.post("/inspections", status_code=status.HTTP_201_CREATED)
def create_inspection(
    payload: InspectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_staff_or_admin(current_user)
    get_authorized_room(db, payload.room_id, current_user)

    inspection = InspectionRecord(
        room_id=payload.room_id,
        inspector_id=current_user.id,
        result=payload.result,
        notes=payload.notes,
    )

    db.add(inspection)
    db.commit()
    db.refresh(inspection)

    return inspection


@router.post("/maintenance-requests", status_code=status.HTTP_201_CREATED)
def create_maintenance_request(
    payload: MaintenanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_staff_or_admin(current_user)
    get_authorized_room(db, payload.room_id, current_user)
    validate_assignee(db, payload.assigned_to)

    maintenance_request = MaintenanceRequest(
        room_id=payload.room_id,
        reported_by=current_user.id,
        assigned_to=payload.assigned_to,
        description=payload.description.strip(),
    )

    db.add(maintenance_request)
    db.commit()
    db.refresh(maintenance_request)

    return maintenance_request


@router.patch("/maintenance-requests/{request_id}/status")
def update_maintenance_status(
    request_id: int,
    payload: MaintenanceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_staff_or_admin(current_user)

    maintenance_request = (
        db.query(MaintenanceRequest)
        .filter(MaintenanceRequest.id == request_id)
        .first()
    )

    if maintenance_request is None:
        raise HTTPException(
            status_code=404,
            detail="Maintenance request not found.",
        )

    if role_value(current_user) == UserRole.HOTEL_STAFF.value:
        if maintenance_request.assigned_to != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Staff can update only maintenance requests assigned to them.",
            )

        if (
            db.query(Room)
            .filter(Room.id == maintenance_request.room_id)
            .first()
            is None
        ):
            raise HTTPException(status_code=404, detail="Room not found.")
    else:
        get_authorized_room(db, maintenance_request.room_id, current_user)

    maintenance_request.status = payload.status
    maintenance_request.completed_at = (
        datetime.now(timezone.utc)
        if payload.status == MaintenanceStatus.COMPLETED
        else None
    )

    db.commit()
    db.refresh(maintenance_request)

    return maintenance_request
