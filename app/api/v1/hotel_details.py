
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.jwt import decode_token
from app.db.session import get_db
from app.models import (
    Amenity,
    Hotel,
    HotelImage,
    HotelReview,
    HotelStatus,
    RoomType,
    User,
    UserRole,
    hotel_amenities,
)
from app.schemas.hotel_details import HotelDetailsResponse
from app.schemas.review import HotelReviewResponse


router = APIRouter(prefix="/hotels", tags=["Hotel Details"])
optional_bearer = HTTPBearer(auto_error=False)


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None

    try:
        payload = decode_token(credentials.credentials)

        if payload.get("type") != "access":
            return None

        user_id = payload.get("sub")
        if user_id is None:
            return None

        user = db.query(User).filter(
            User.id == int(user_id)
        ).first()

        if user is None or not user.is_active:
            return None

        return user

    except Exception:
        return None


@router.get(
    "/{hotel_id}/details",
    response_model=HotelDetailsResponse,
)
def get_hotel_details(
    hotel_id: int,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    hotel = db.query(Hotel).filter(
        Hotel.id == hotel_id
    ).first()

    if hotel is None:
        raise HTTPException(
            status_code=404,
            detail="Hotel not found",
        )

    is_owner = (
        current_user is not None
        and current_user.role == UserRole.HOTEL_OWNER
        and current_user.id == hotel.owner_id
    )

    # Only approved hotels are publicly visible.
    # Owners may view their own unpublished hotels.
    if hotel.status != HotelStatus.APPROVED and not is_owner:
        raise HTTPException(
            status_code=404,
            detail="Hotel not found",
        )

    room_types = (
        db.query(RoomType)
        .filter(RoomType.hotel_id == hotel_id)
        .order_by(RoomType.id)
        .all()
    )

    amenities = (
        db.query(Amenity)
        .join(
            hotel_amenities,
            hotel_amenities.c.amenity_id == Amenity.id,
        )
        .filter(hotel_amenities.c.hotel_id == hotel_id)
        .order_by(Amenity.name)
        .all()
    )

    gallery = (
        db.query(HotelImage)
        .filter(HotelImage.hotel_id == hotel_id)
        .order_by(
            HotelImage.is_primary.desc(),
            HotelImage.display_order.asc(),
            HotelImage.id.asc(),
        )
        .all()
    )

    reviews = (
        db.query(HotelReview)
        .filter(HotelReview.hotel_id == hotel_id)
        .order_by(
            HotelReview.created_at.desc(),
            HotelReview.id.desc(),
        )
        .all()
    )

    return {
        "id": hotel.id,
        "name": hotel.name,
        "description": hotel.description,
        "property_type": hotel.property_type,
        "rating": hotel.rating,
        "address": hotel.address,
        "city": hotel.city,
        "state": hotel.state,
        "postal_code": hotel.postal_code,
        "country": hotel.country,
        "latitude": hotel.latitude,
        "longitude": hotel.longitude,
        "policies": hotel.policies,
        "check_in_time": hotel.check_in_time,
        "check_out_time": hotel.check_out_time,
        "check_in_rules": hotel.check_in_rules,
        "room_types": room_types,
        "amenities": amenities,
        "gallery": gallery,
        "reviews": [
            HotelReviewResponse.model_validate(review).model_dump()
            for review in reviews
        ],
    }
