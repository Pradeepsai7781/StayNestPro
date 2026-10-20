
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import Hotel, RoomType, User, UserRole
from app.schemas.room_type import (
    RoomTypeCreate,
    RoomTypeResponse,
    RoomTypeUpdate,
)


router = APIRouter(
    prefix="/hotels/{hotel_id}/room-types",
    tags=["Room Types"],
)


def get_owned_hotel(
    hotel_id: int,
    current_user: User,
    db: Session,
) -> Hotel:
    if current_user.role != UserRole.HOTEL_OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only hotel owners can manage room types",
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
            detail="Hotel not found",
        )

    return hotel


def get_hotel_room_type(
    hotel_id: int,
    room_type_id: int,
    db: Session,
) -> RoomType:
    room_type = (
        db.query(RoomType)
        .filter(
            RoomType.id == room_type_id,
            RoomType.hotel_id == hotel_id,
        )
        .first()
    )

    if room_type is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room type not found",
        )

    return room_type


@router.post(
    "",
    response_model=RoomTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_room_type(
    hotel_id: int,
    room_type_data: RoomTypeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hotel = get_owned_hotel(hotel_id, current_user, db)

    existing = (
        db.query(RoomType)
        .filter(
            RoomType.hotel_id == hotel.id,
            RoomType.name == room_type_data.name,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This room type already exists for this hotel",
        )

    room_type = RoomType(
        hotel_id=hotel.id,
        **room_type_data.model_dump(),
    )

    try:
        db.add(room_type)
        db.commit()
        db.refresh(room_type)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not create room type because of a database constraint",
        )

    return room_type


@router.get("", response_model=list[RoomTypeResponse])
def list_room_types(
    hotel_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hotel = get_owned_hotel(hotel_id, current_user, db)

    return (
        db.query(RoomType)
        .filter(RoomType.hotel_id == hotel.id)
        .order_by(RoomType.id)
        .all()
    )


@router.get("/{room_type_id}", response_model=RoomTypeResponse)
def get_room_type(
    hotel_id: int,
    room_type_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_owned_hotel(hotel_id, current_user, db)
    return get_hotel_room_type(hotel_id, room_type_id, db)


@router.patch("/{room_type_id}", response_model=RoomTypeResponse)
def update_room_type(
    hotel_id: int,
    room_type_id: int,
    room_type_data: RoomTypeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_owned_hotel(hotel_id, current_user, db)
    room_type = get_hotel_room_type(hotel_id, room_type_id, db)

    update_data = room_type_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if value is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field} cannot be null",
            )

    if "name" in update_data:
        duplicate = (
            db.query(RoomType)
            .filter(
                RoomType.hotel_id == hotel_id,
                RoomType.name == update_data["name"],
                RoomType.id != room_type_id,
            )
            .first()
        )

        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This room type already exists for this hotel",
            )

    for field, value in update_data.items():
        setattr(room_type, field, value)

    try:
        db.commit()
        db.refresh(room_type)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not update room type because of a database constraint",
        )

    return room_type


@router.delete("/{room_type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room_type(
    hotel_id: int,
    room_type_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_owned_hotel(hotel_id, current_user, db)
    room_type = get_hotel_room_type(hotel_id, room_type_id, db)

    db.delete(room_type)
    db.commit()

    return None
