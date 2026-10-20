
import math
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import (
    Amenity,
    Hotel,
    HotelStatus,
    PropertyType,
    Reservation,
    ReservationStatus,
    Room,
    RoomStatus,
    RoomType,
)


router = APIRouter(
    prefix="/hotels",
    tags=["Hotel Search"],
)


@router.get("/search")
def search_hotels(
    name: str | None = Query(default=None, min_length=1, max_length=150),
    city: str | None = Query(default=None, min_length=1, max_length=100),
    state: str | None = Query(default=None, min_length=1, max_length=100),
    country: str | None = Query(default=None, min_length=1, max_length=100),
    room_type: str | None = Query(default=None),
    guests: int | None = Query(default=None, ge=1, le=100),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    min_rating: float | None = Query(default=None, ge=0, le=5),
    property_type: str | None = Query(default=None),
    amenities: list[str] | None = Query(default=None),
    check_in: date | None = Query(default=None),
    check_out: date | None = Query(default=None),
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    radius_km: float = Query(default=25, gt=0, le=500),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    sort_by: str = Query(default="name"),
    order: str = Query(default="asc"),
    db: Session = Depends(get_db),
):
    """Search approved hotels with basic and advanced filters."""

    allowed_sort_fields = {
        "name": Hotel.name,
        "city": Hotel.city,
        "created_at": Hotel.created_at,
        "rating": Hotel.rating,
    }

    sort_by = sort_by.strip().lower()
    order = order.strip().lower()

    if sort_by not in allowed_sort_fields:
        raise HTTPException(
            status_code=422,
            detail="sort_by must be name, city, created_at, or rating",
        )

    if order not in {"asc", "desc"}:
        raise HTTPException(
            status_code=422,
            detail="order must be asc or desc",
        )

    if min_price is not None and max_price is not None:
        if min_price > max_price:
            raise HTTPException(
                status_code=422,
                detail="min_price cannot be greater than max_price",
            )

    if (latitude is None) != (longitude is None):
        raise HTTPException(
            status_code=422,
            detail="Provide both latitude and longitude for nearby search",
        )

    if (check_in is None) != (check_out is None):
        raise HTTPException(
            status_code=422,
            detail="Provide both check_in and check_out",
        )

    if check_in is not None and check_out is not None:
        if check_in < date.today():
            raise HTTPException(
                status_code=422,
                detail="check_in cannot be in the past",
            )
        if check_out <= check_in:
            raise HTTPException(
                status_code=422,
                detail="check_out must be after check_in",
            )

    valid_room_types = {
        "SINGLE",
        "DOUBLE",
        "DELUXE",
        "SUITE",
        "FAMILY",
    }

    normalized_room_type = None
    if room_type:
        normalized_room_type = room_type.strip().upper()
        if normalized_room_type not in valid_room_types:
            raise HTTPException(
                status_code=422,
                detail="room_type must be SINGLE, DOUBLE, DELUXE, SUITE, or FAMILY",
            )

    normalized_property_type = None
    if property_type:
        normalized_property_type = property_type.strip().upper()
        valid_property_types = {item.value for item in PropertyType}
        if normalized_property_type not in valid_property_types:
            raise HTTPException(
                status_code=422,
                detail=(
                    "property_type must be HOTEL, RESORT, GUEST_HOUSE, "
                    "HOSTEL, HOMESTAY, or VILLA"
                ),
            )

    normalized_amenities = []
    if amenities:
        normalized_amenities = [
            item.strip() for item in amenities if item.strip()
        ]
        if not normalized_amenities:
            raise HTTPException(
                status_code=422,
                detail="Provide at least one non-empty amenity",
            )

    query = db.query(Hotel).filter(
        Hotel.status == HotelStatus.APPROVED
    )

    if name:
        query = query.filter(Hotel.name.ilike(f"%{name.strip()}%"))

    if city:
        query = query.filter(Hotel.city.ilike(f"%{city.strip()}%"))

    if state:
        query = query.filter(Hotel.state.ilike(f"%{state.strip()}%"))

    if country:
        query = query.filter(Hotel.country.ilike(f"%{country.strip()}%"))

    if normalized_property_type:
        query = query.filter(
            Hotel.property_type == PropertyType(normalized_property_type)
        )

    if min_rating is not None:
        query = query.filter(
            Hotel.rating.isnot(None),
            Hotel.rating >= min_rating,
        )

    # Price, room type, and guest capacity must match the same room type.
    if (
        min_price is not None
        or max_price is not None
        or normalized_room_type is not None
        or guests is not None
    ):
        room_type_query = db.query(RoomType.hotel_id).filter(
            RoomType.capacity >= (guests if guests is not None else 1)
        )

        if min_price is not None:
            room_type_query = room_type_query.filter(
                RoomType.price_per_night >= min_price
            )

        if max_price is not None:
            room_type_query = room_type_query.filter(
                RoomType.price_per_night <= max_price
            )

        if normalized_room_type:
            room_type_query = room_type_query.filter(
                RoomType.name == normalized_room_type
            )

        query = query.filter(Hotel.id.in_(room_type_query))

    # Each requested amenity must be present at the hotel.
    for amenity_name in normalized_amenities:
        matching_hotel_ids = (
            db.query(Hotel.id)
            .join(
                Hotel.amenities if hasattr(Hotel, "amenities") else
                # Use the existing association table when no ORM relationship exists.
                Amenity,
                False,
            )
        ) if False else None

        amenity = (
            db.query(Amenity)
            .filter(func.lower(Amenity.name) == amenity_name.lower())
            .first()
        )

        if amenity is None:
            query = query.filter(Hotel.id == -1)
            continue

        from app.models.amenity import hotel_amenities

        query = query.filter(
            Hotel.id.in_(
                db.query(hotel_amenities.c.hotel_id).filter(
                    hotel_amenities.c.amenity_id == amenity.id
                )
            )
        )

    # Find rooms with no overlapping confirmed reservations for the dates.
    if check_in is not None and check_out is not None:
        reserved_room_ids = (
            db.query(Reservation.room_id)
            .filter(
                Reservation.status == ReservationStatus.CONFIRMED,
                Reservation.check_in < check_out,
                Reservation.check_out > check_in,
            )
            .distinct()
            .subquery()
        )

        available_room_ids = (
            db.query(Room.hotel_id)
            .filter(
                Room.status == RoomStatus.AVAILABLE,
                ~Room.id.in_(reserved_room_ids),
            )
            .distinct()
            .subquery()
        )

        query = query.filter(Hotel.id.in_(available_room_ids))

    distance_expression = None

    if latitude is not None and longitude is not None:
        lat_rad = math.radians(latitude)

        distance_expression = (
            6371
            * 2
            * func.asin(
                func.sqrt(
                    func.least(
                        1.0,
                        func.pow(
                            func.sin(
                                (
                                    func.radians(Hotel.latitude) - lat_rad
                                ) / 2
                            ),
                            2,
                        )
                        + func.cos(lat_rad)
                        * func.cos(func.radians(Hotel.latitude))
                        * func.pow(
                            func.sin(
                                (
                                    func.radians(Hotel.longitude)
                                    - math.radians(longitude)
                                ) / 2
                            ),
                            2,
                        ),
                    )
                )
            )
        )

        query = query.filter(
            Hotel.latitude.isnot(None),
            Hotel.longitude.isnot(None),
            distance_expression <= radius_km,
        )

    total = query.count()

    if distance_expression is not None:
        query = query.order_by(distance_expression.asc())
    else:
        sort_column = allowed_sort_fields[sort_by]
        query = query.order_by(
            sort_column.asc() if order == "asc" else sort_column.desc()
        )

    hotels = (
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    results = []

    for hotel in hotels:
        item = {
            "id": hotel.id,
            "name": hotel.name,
            "description": hotel.description,
            "address": hotel.address,
            "city": hotel.city,
            "state": hotel.state,
            "postal_code": hotel.postal_code,
            "country": hotel.country,
            "latitude": hotel.latitude,
            "longitude": hotel.longitude,
            "property_type": hotel.property_type.value,
            "rating": hotel.rating,
        }

        if distance_expression is not None:
            # Haversine distance for the returned result.
            hotel_lat = math.radians(hotel.latitude)
            hotel_lon = math.radians(hotel.longitude)
            query_lat = math.radians(latitude)
            query_lon = math.radians(longitude)

            haversine_a = (
                math.sin((hotel_lat - query_lat) / 2) ** 2
                + math.cos(query_lat)
                * math.cos(hotel_lat)
                * math.sin((hotel_lon - query_lon) / 2) ** 2
            )

            haversine_a = min(1.0, max(0.0, haversine_a))
            item["distance_km"] = round(
                6371 * 2 * math.asin(math.sqrt(haversine_a)),
                2,
            )

        results.append(item)

    return {
        "items": results,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total else 0,
    }
