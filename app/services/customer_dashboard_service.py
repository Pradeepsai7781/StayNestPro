
from datetime import date

from sqlalchemy.orm import Session

from app.models import (
    FavoriteHotel,
    FavoriteRoom,
    Hotel,
    Notification,
    Payment,
    Reservation,
    ReservationStatus,
    Room,
)
from app.services.recommendation_service import get_recommendations


def get_customer_dashboard(db: Session, user_id: int) -> dict:
    """Return dashboard information belonging to one customer."""

    today = date.today()

    # 1. Upcoming bookings and booking history
    reservations = (
        db.query(Reservation)
        .filter(Reservation.customer_id == user_id)
        .order_by(Reservation.check_in.asc())
        .all()
    )

    upcoming_bookings = []
    booking_history = []

    for reservation in reservations:
        booking = {
            "id": reservation.id,
            "room_id": reservation.room_id,
            "customer_id": reservation.customer_id,
            "check_in": reservation.check_in,
            "check_out": reservation.check_out,
            "guest_count": reservation.guest_count,
            "booking_reference": reservation.booking_reference,
            "total_price": float(reservation.total_price),
            "status": (
                reservation.status.value
                if hasattr(reservation.status, "value")
                else str(reservation.status)
            ),
            "created_at": reservation.created_at,
        }

        if (
            reservation.status == ReservationStatus.CONFIRMED
            and reservation.check_out >= today
        ):
            upcoming_bookings.append(booking)
        else:
            booking_history.append(booking)

    # 2. Hotel wishlist
    hotel_wishlist = (
        db.query(FavoriteHotel, Hotel)
        .join(Hotel, Hotel.id == FavoriteHotel.hotel_id)
        .filter(FavoriteHotel.user_id == user_id)
        .order_by(FavoriteHotel.created_at.desc())
        .all()
    )

    hotel_wishlist_data = [
        {
            "favorite_id": favorite.id,
            "hotel_id": hotel.id,
            "hotel_name": hotel.name,
            "city": hotel.city,
            "country": hotel.country,
            "created_at": favorite.created_at,
        }
        for favorite, hotel in hotel_wishlist
    ]

    # 3. Room wishlist
    room_wishlist = (
        db.query(FavoriteRoom, Room, Hotel)
        .join(Room, Room.id == FavoriteRoom.room_id)
        .join(Hotel, Hotel.id == Room.hotel_id)
        .filter(FavoriteRoom.user_id == user_id)
        .order_by(FavoriteRoom.created_at.desc())
        .all()
    )

    room_wishlist_data = [
        {
            "favorite_id": favorite.id,
            "room_id": room.id,
            "hotel_id": hotel.id,
            "hotel_name": hotel.name,
            "room_number": room.room_number,
            "created_at": favorite.created_at,
        }
        for favorite, room, hotel in room_wishlist
    ]

    # 4. Payment history
    payments = (
        db.query(Payment)
        .filter(Payment.customer_id == user_id)
        .order_by(Payment.created_at.desc())
        .all()
    )

    payment_history = [
        {
            "id": payment.id,
            "reservation_id": payment.reservation_id,
            "customer_id": payment.customer_id,
            "amount": float(payment.amount),
            "currency": payment.currency,
            "status": (
                payment.status.value
                if hasattr(payment.status, "value")
                else str(payment.status)
            ),
            "created_at": payment.created_at,
            "updated_at": payment.updated_at,
        }
        for payment in payments
    ]

    # 5. Notifications
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .all()
    )

    notification_data = [
        {
            "id": notification.id,
            "title": notification.title,
            "message": notification.message,
            "notification_type": notification.notification_type,
            "is_read": notification.is_read,
            "related_reservation_id": (
                notification.related_reservation_id
            ),
            "created_at": notification.created_at,
            "read_at": notification.read_at,
        }
        for notification in notifications
    ]

    # 6. Recommended hotels
    recommended_hotels = get_recommendations(
        db=db,
        user_id=user_id,
        limit=10,
    )

    return {
        "upcoming_bookings": upcoming_bookings,
        "booking_history": booking_history,
        "hotel_wishlist": hotel_wishlist_data,
        "room_wishlist": room_wishlist_data,
        "payment_history": payment_history,
        "notifications": notification_data,
        "recommended_hotels": recommended_hotels,
    }

