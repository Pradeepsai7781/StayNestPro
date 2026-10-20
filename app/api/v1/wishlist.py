
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.db.session import get_db
from app.models import (
    FavoriteHotel,
    FavoriteRoom,
    Hotel,
    Room,
    User,
    UserRole,
)

router = APIRouter(prefix="/wishlist", tags=["Wishlist"])

require_customer = require_roles(UserRole.CUSTOMER)


# Add a hotel to the customer's wishlist
@router.post(
    "/hotels/{hotel_id}",
    status_code=status.HTTP_201_CREATED,
)
def add_favorite_hotel(
    hotel_id: int,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()

    if hotel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hotel not found.",
        )

    existing = (
        db.query(FavoriteHotel)
        .filter(
            FavoriteHotel.user_id == current_user.id,
            FavoriteHotel.hotel_id == hotel_id,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Hotel is already in your wishlist.",
        )

    favorite = FavoriteHotel(
        user_id=current_user.id,
        hotel_id=hotel_id,
    )
    db.add(favorite)

    try:
        db.commit()
        db.refresh(favorite)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Hotel is already in your wishlist.",
        )

    return {
        "message": "Hotel added to wishlist.",
        "favorite_id": favorite.id,
        "hotel_id": favorite.hotel_id,
    }


# Remove a hotel from the customer's wishlist
@router.delete("/hotels/{hotel_id}")
def remove_favorite_hotel(
    hotel_id: int,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    favorite = (
        db.query(FavoriteHotel)
        .filter(
            FavoriteHotel.user_id == current_user.id,
            FavoriteHotel.hotel_id == hotel_id,
        )
        .first()
    )

    if favorite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hotel is not in your wishlist.",
        )

    db.delete(favorite)
    db.commit()

    return {"message": "Hotel removed from wishlist."}


# Retrieve the customer's hotel wishlist
@router.get("/hotels")
def get_favorite_hotels(
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    favorites = (
        db.query(FavoriteHotel, Hotel)
        .join(Hotel, Hotel.id == FavoriteHotel.hotel_id)
        .filter(FavoriteHotel.user_id == current_user.id)
        .order_by(FavoriteHotel.created_at.desc())
        .all()
    )

    return [
        {
            "favorite_id": favorite.id,
            "hotel_id": hotel.id,
            "hotel_name": hotel.name,
            "created_at": favorite.created_at,
        }
        for favorite, hotel in favorites
    ]


# Add a room to the customer's favorites
@router.post(
    "/rooms/{room_id}",
    status_code=status.HTTP_201_CREATED,
)
def add_favorite_room(
    room_id: int,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    room = db.query(Room).filter(Room.id == room_id).first()

    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found.",
        )

    existing = (
        db.query(FavoriteRoom)
        .filter(
            FavoriteRoom.user_id == current_user.id,
            FavoriteRoom.room_id == room_id,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Room is already in your favorites.",
        )

    favorite = FavoriteRoom(
        user_id=current_user.id,
        room_id=room_id,
    )
    db.add(favorite)

    try:
        db.commit()
        db.refresh(favorite)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Room is already in your favorites.",
        )

    return {
        "message": "Room added to favorites.",
        "favorite_id": favorite.id,
        "room_id": favorite.room_id,
    }


# Remove a room from the customer's favorites
@router.delete("/rooms/{room_id}")
def remove_favorite_room(
    room_id: int,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    favorite = (
        db.query(FavoriteRoom)
        .filter(
            FavoriteRoom.user_id == current_user.id,
            FavoriteRoom.room_id == room_id,
        )
        .first()
    )

    if favorite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room is not in your favorites.",
        )

    db.delete(favorite)
    db.commit()

    return {"message": "Room removed from favorites."}


# Retrieve the customer's favorite rooms
@router.get("/rooms")
def get_favorite_rooms(
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    favorites = (
        db.query(FavoriteRoom, Room)
        .join(Room, Room.id == FavoriteRoom.room_id)
        .filter(FavoriteRoom.user_id == current_user.id)
        .order_by(FavoriteRoom.created_at.desc())
        .all()
    )

    return [
        {
            "favorite_id": favorite.id,
            "room_id": room.id,
            "hotel_id": room.hotel_id,
            "room_number": room.room_number,
            "created_at": favorite.created_at,
        }
        for favorite, room in favorites
    ]
