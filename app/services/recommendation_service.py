
from sqlalchemy.orm import Session

from app.models import (
    FavoriteHotel,
    Hotel,
    HotelStatus,
    Reservation,
    ReservationStatus,
    Room,
    RoomType,
    FavoriteRoom,
)


def get_recommendations(
    db: Session,
    user_id: int,
    budget: float | None = None,
    city: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Recommend approved hotels using booking history and preferences."""

    query = db.query(Hotel).filter(
        Hotel.status == HotelStatus.APPROVED
    )

    if city:
        query = query.filter(Hotel.city.ilike(f"%{city.strip()}%"))

    if budget is not None:
        affordable_hotel_ids = (
            db.query(RoomType.hotel_id)
            .filter(RoomType.price_per_night <= budget)
            .distinct()
        )
        query = query.filter(Hotel.id.in_(affordable_hotel_ids))

    bookings = (
        db.query(Reservation, Room)
        .join(Room, Room.id == Reservation.room_id)
        .filter(
            Reservation.customer_id == user_id,
            Reservation.status.in_(
                [ReservationStatus.CONFIRMED, ReservationStatus.COMPLETED]
            ),
        )
        .all()
    )

    preferred_hotel_ids = {room.hotel_id for _, room in bookings}

    favorite_hotel_ids = {
        row.hotel_id
        for row in db.query(FavoriteHotel)
        .filter(FavoriteHotel.user_id == user_id)
        .all()
    }

    favorite_room_ids = {
        row.room_id
        for row in db.query(FavoriteRoom)
        .filter(FavoriteRoom.user_id == user_id)
        .all()
    }

    favorite_room_hotel_ids = {
        room.hotel_id
        for room in db.query(Room)
        .filter(Room.id.in_(favorite_room_ids))
        .all()
    } if favorite_room_ids else set()

    results = []

    for hotel in query.all():
        score = 0
        reasons = []

        if hotel.id in favorite_hotel_ids:
            score += 5
            reasons.append("Based on your favorite hotels")

        if hotel.id in preferred_hotel_ids:
            score += 3
            reasons.append("Based on your booking history")

        if hotel.id in favorite_room_hotel_ids:
            score += 3
            reasons.append("Based on your favorite rooms")

        if hotel.rating is not None:
            score += hotel.rating
            reasons.append("Hotel rating")

        if budget is not None:
            cheapest_price = (
                db.query(RoomType.price_per_night)
                .filter(RoomType.hotel_id == hotel.id)
                .order_by(RoomType.price_per_night.asc())
                .first()
            )
            if cheapest_price:
                score += 2
                reasons.append("Within your budget")

        results.append(
            {
                "hotel_id": hotel.id,
                "name": hotel.name,
                "city": hotel.city,
                "country": hotel.country,
                "property_type": hotel.property_type.value,
                "rating": hotel.rating,
                "recommendation_score": round(score, 2),
                "reasons": reasons,
            }
        )

    results.sort(
        key=lambda item: (
            item["recommendation_score"],
            item["rating"] or 0,
        ),
        reverse=True,
    )

    return results[:limit]


def get_similar_hotels(
    db: Session,
    hotel_id: int,
    limit: int = 5,
) -> list[dict]:
    """Find approved hotels in the same city and property category."""

    hotel = (
        db.query(Hotel)
        .filter(
            Hotel.id == hotel_id,
            Hotel.status == HotelStatus.APPROVED,
        )
        .first()
    )

    if hotel is None:
        return []

    similar = (
        db.query(Hotel)
        .filter(
            Hotel.status == HotelStatus.APPROVED,
            Hotel.id != hotel.id,
            (
                (Hotel.city == hotel.city)
                | (Hotel.property_type == hotel.property_type)
            ),
        )
        .order_by(Hotel.rating.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "hotel_id": item.id,
            "name": item.name,
            "city": item.city,
            "country": item.country,
            "property_type": item.property_type.value,
            "rating": item.rating,
        }
        for item in similar
    ]
