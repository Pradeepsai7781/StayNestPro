
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import Hotel, Room, RoomType, User, UserRole
from app.schemas.room import RoomCreate, RoomResponse, RoomUpdate


router = APIRouter(
    prefix="/hotels/{hotel_id}/rooms",
    tags=["Rooms"],
)


def get_owned_hotel(
    hotel_id: int,
    current_user: User,
    db: Session,
) -> Hotel:
    if current_user.role != UserRole.HOTEL_OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only hotel owners can manage rooms.",
        )

    hotel = (
        db.query(Hotel)
        .filter(
            Hotel.id == hotel_id,
            Hotel.owner_id == current_user.id,
        )
        .first()
    )

    if hotel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hotel not found or you do not own this hotel.",
        )

    return hotel


@router.post(
    "",
    response_model=RoomResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_room(
    hotel_id: int,
    payload: RoomCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_hotel(hotel_id, current_user, db)

    room_number = payload.room_number.strip()

    if not room_number:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Room number cannot be empty.",
        )

    existing_room = (
        db.query(Room)
        .filter(
            Room.hotel_id == hotel_id,
            Room.room_number == room_number,
        )
        .first()
    )

    if existing_room:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A room with this number already exists in this hotel.",
        )

    room_type = (
        db.query(RoomType)
        .filter(
            RoomType.id == payload.room_type_id,
            RoomType.hotel_id == hotel_id,
        )
        .first()
    )

    if room_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid room type for this hotel.",
        )

    if payload.capacity > room_type.capacity:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Room capacity cannot exceed room type capacity.",
        )

    room = Room(
        hotel_id=hotel_id,
        room_type_id=payload.room_type_id,
        room_number=room_number,
        capacity=payload.capacity,
        status=payload.status,
    )

    try:
        db.add(room)
        db.commit()
        db.refresh(room)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Room could not be created because of a conflicting record.",
        )

    return room


@router.get(
    "",
    response_model=list[RoomResponse],
)
def list_rooms(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_hotel(hotel_id, current_user, db)

    return (
        db.query(Room)
        .filter(Room.hotel_id == hotel_id)
        .order_by(Room.room_number.asc())
        .all()
    )


@router.get(
    "/{room_id}",
    response_model=RoomResponse,
)
def get_room(
    hotel_id: int,
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_hotel(hotel_id, current_user, db)

    room = (
        db.query(Room)
        .filter(
            Room.id == room_id,
            Room.hotel_id == hotel_id,
        )
        .first()
    )

    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found.",
        )

    return room


@router.patch(
    "/{room_id}",
    response_model=RoomResponse,
)
def update_room(
    hotel_id: int,
    room_id: int,
    payload: RoomUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_hotel(hotel_id, current_user, db)

    room = (
        db.query(Room)
        .filter(
            Room.id == room_id,
            Room.hotel_id == hotel_id,
        )
        .first()
    )

    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found.",
        )

    update_data = payload.model_dump(exclude_unset=True)

    if "room_number" in update_data:
        room_number = update_data["room_number"]

        if room_number is None or not room_number.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Room number cannot be empty.",
            )

        room_number = room_number.strip()

        duplicate = (
            db.query(Room)
            .filter(
                Room.hotel_id == hotel_id,
                Room.room_number == room_number,
                Room.id != room_id,
            )
            .first()
        )

        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A room with this number already exists in this hotel.",
            )

        update_data["room_number"] = room_number

    new_capacity = update_data.get("capacity", room.capacity)
    new_room_type_id = update_data.get("room_type_id", room.room_type_id)

    room_type = (
        db.query(RoomType)
        .filter(
            RoomType.id == new_room_type_id,
            RoomType.hotel_id == hotel_id,
        )
        .first()
    )

    if room_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid room type for this hotel.",
        )

    if new_capacity > room_type.capacity:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Room capacity cannot exceed room type capacity.",
        )

    for field, value in update_data.items():
        setattr(room, field, value)

    try:
        db.commit()
        db.refresh(room)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Room could not be updated because of a conflicting record.",
        )

    return room


@router.delete(
    "/{room_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_room(
    hotel_id: int,
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_hotel(hotel_id, current_user, db)

    room = (
        db.query(Room)
        .filter(
            Room.id == room_id,
            Room.hotel_id == hotel_id,
        )
        .first()
    )

    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found.",
        )

    try:
        db.delete(room)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Room cannot be deleted because it has associated records.",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
