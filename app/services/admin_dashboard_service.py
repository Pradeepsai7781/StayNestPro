
from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Hotel,
    HotelStatus,
    Payment,
    PaymentStatus,
    Reservation,
    ReservationStatus,
    Room,
    User,
    UserRole,
)


def get_admin_dashboard(
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
    hotel_id: int | None = None,
    status: str | None = None,
) -> dict:
    """Return platform-wide admin dashboard metrics and active reservations."""

    today = date.today()

    # Platform-wide counts
    total_customers = (
        db.query(func.count(User.id))
        .filter(User.role == UserRole.CUSTOMER)
        .scalar()
        or 0
    )

    total_hotels = db.query(func.count(Hotel.id)).scalar() or 0
    total_rooms = db.query(func.count(Room.id)).scalar() or 0

    booking_query = db.query(Reservation)

    if start_date:
        booking_query = booking_query.filter(
            Reservation.check_in >= start_date
        )

    if end_date:
        booking_query = booking_query.filter(
            Reservation.check_in <= end_date
        )

    if hotel_id is not None:
        booking_query = booking_query.join(
            Room, Room.id == Reservation.room_id
        ).filter(Room.hotel_id == hotel_id)

    if status:
        booking_query = booking_query.filter(
            Reservation.status == status.upper()
        )

    total_bookings = booking_query.count()

    # Revenue from successful payments, with matching dashboard filters.
    revenue_query = db.query(
        func.coalesce(func.sum(Payment.amount), 0)
    ).join(
        Reservation, Reservation.id == Payment.reservation_id
    ).filter(
        Payment.status == PaymentStatus.SUCCEEDED
    )

    if start_date:
        revenue_query = revenue_query.filter(
            Payment.created_at >= datetime.combine(
                start_date, time.min, tzinfo=timezone.utc
            )
        )

    if end_date:
        revenue_query = revenue_query.filter(
            Payment.created_at < datetime.combine(
                end_date, time.max, tzinfo=timezone.utc
            )
        )

    if hotel_id is not None:
        revenue_query = revenue_query.join(
            Room, Room.id == Reservation.room_id
        ).filter(Room.hotel_id == hotel_id)

    platform_revenue = revenue_query.scalar() or Decimal("0.00")

    # Active reservations: confirmed stays that include today's date.
    active_query = db.query(Reservation).filter(
        Reservation.status == ReservationStatus.CONFIRMED,
        Reservation.check_in <= today,
        Reservation.check_out > today,
    )

    if start_date:
        active_query = active_query.filter(
            Reservation.check_in >= start_date
        )

    if end_date:
        active_query = active_query.filter(
            Reservation.check_in <= end_date
        )

    if hotel_id is not None:
        active_query = active_query.join(
            Room, Room.id == Reservation.room_id
        ).filter(Room.hotel_id == hotel_id)

    if status:
        active_query = active_query.filter(
            Reservation.status == status.upper()
        )

    active_reservations = active_query.order_by(
        Reservation.check_in.asc()
    ).all()

    active_reservation_details = [
        {
            "reservation_id": reservation.id,
            "booking_reference": reservation.booking_reference,
            "customer_id": reservation.customer_id,
            "room_id": reservation.room_id,
            "check_in": reservation.check_in,
            "check_out": reservation.check_out,
            "total_price": float(reservation.total_price),
            "status": reservation.status.value,
        }
        for reservation in active_reservations
    ]

    return {
        "summary": {
            "total_customers": total_customers,
            "total_hotels": total_hotels,
            "total_rooms": total_rooms,
            "total_bookings": total_bookings,
            "platform_revenue": float(platform_revenue),
            "active_reservations": len(active_reservation_details),
        },
        "start_date": start_date,
        "end_date": end_date,
        "hotel_id": hotel_id,
        "status": status.upper() if status else None,
        "active_reservation_details": active_reservation_details,
    }
