
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.reservation import Reservation
from app.models.payment import Payment
from app.models.hotel import Hotel
from app.models.room import Room

from app.services.revenue_analytics_service import (
    get_revenue_for_period,
    get_daily_revenue,
)
from app.services.occupancy_analytics_service import (
    get_occupancy_summary,
)
from app.services.customer_analytics_service import (
    get_customer_analytics,
)


REPORT_TYPES = {
    "bookings",
    "revenue",
    "occupancy",
    "customers",
    "hotels",
    "payments",
}


def _date_bounds(start_date: date, end_date: date):
    start = datetime.combine(
        start_date,
        time.min,
        tzinfo=timezone.utc,
    )
    end = datetime.combine(
        end_date + timedelta(days=1),
        time.min,
        tzinfo=timezone.utc,
    )
    return start, end


def _validate_dates(start_date: date, end_date: date):
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date.")

    if (end_date - start_date).days > 365:
        raise ValueError("The date range cannot exceed 366 days.")


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def _decimal_value(value):
    return str(value if value is not None else Decimal("0.00"))


def get_booking_report(
    db: Session,
    start_date: date,
    end_date: date,
):
    start, end = _date_bounds(start_date, end_date)

    rows = (
        db.query(Reservation, User, Room, Hotel)
        .join(User, User.id == Reservation.customer_id)
        .join(Room, Room.id == Reservation.room_id)
        .join(Hotel, Hotel.id == Room.hotel_id)
        .filter(
            Reservation.created_at >= start,
            Reservation.created_at < end,
        )
        .order_by(Reservation.created_at.desc())
        .all()
    )

    return [
        {
            "reservation_id": reservation.id,
            "booking_reference": reservation.booking_reference,
            "customer_id": user.id,
            "customer_name": user.full_name,
            "hotel_id": hotel.id,
            "hotel_name": hotel.name,
            "room_id": room.id,
            "check_in": reservation.check_in.isoformat(),
            "check_out": reservation.check_out.isoformat(),
            "guest_count": reservation.guest_count,
            "total_price": _decimal_value(reservation.total_price),
            "status": _enum_value(reservation.status),
            "created_at": reservation.created_at.isoformat(),
        }
        for reservation, user, room, hotel in rows
    ]


def get_revenue_report(
    db: Session,
    start_date: date,
    end_date: date,
):
    daily_results = get_daily_revenue(
        db,
        start_date,
        end_date,
    )

    return [
        {
            key: (
                value.isoformat()
                if isinstance(value, date)
                else _decimal_value(value)
                if isinstance(value, Decimal)
                else value
            )
            for key, value in item.items()
        }
        for item in daily_results
    ]


def get_occupancy_report(
    db: Session,
    start_date: date,
    end_date: date,
):
    summary = get_occupancy_summary(
        db=db,
        start_date=start_date,
        end_date=end_date,
    )

    return [
        {
            key: (
                value.isoformat()
                if isinstance(value, date)
                else value
            )
            for key, value in item.items()
        }
        for item in summary["daily_summaries"]
    ]


def get_customer_report(
    db: Session,
    start_date: date,
    end_date: date,
):
    analytics = get_customer_analytics(
        db=db,
        start_date=start_date,
        end_date=end_date,
    )

    return [
        {
            "customer_id": customer.customer_id,
            "customer_name": customer.customer_name,
            "booking_frequency": customer.booking_frequency,
            "total_spending": _decimal_value(
                customer.total_spending
            ),
            "average_spending": _decimal_value(
                customer.average_spending
            ),
            "is_repeat_customer": customer.is_repeat_customer,
        }
        for customer in analytics.customers
    ]


def get_hotel_report(
    db: Session,
    start_date: date,
    end_date: date,
):
    start, end = _date_bounds(start_date, end_date)

    hotels = (
        db.query(Hotel)
        .filter(
            Hotel.created_at >= start,
            Hotel.created_at < end,
        )
        .order_by(Hotel.created_at.desc())
        .all()
    )

    return [
        {
            "hotel_id": hotel.id,
            "hotel_name": hotel.name,
            "owner_id": hotel.owner_id,
            "city": hotel.city,
            "state": hotel.state,
            "country": hotel.country,
            "property_type": _enum_value(hotel.property_type),
            "status": _enum_value(hotel.status),
            "is_reported": hotel.is_reported,
            "created_at": hotel.created_at.isoformat(),
        }
        for hotel in hotels
    ]


def get_payment_report(
    db: Session,
    start_date: date,
    end_date: date,
):
    start, end = _date_bounds(start_date, end_date)

    rows = (
        db.query(Payment, Reservation, User)
        .join(
            Reservation,
            Reservation.id == Payment.reservation_id,
        )
        .join(User, User.id == Payment.customer_id)
        .filter(
            Payment.created_at >= start,
            Payment.created_at < end,
        )
        .order_by(Payment.created_at.desc())
        .all()
    )

    return [
        {
            "payment_id": payment.id,
            "reservation_id": reservation.id,
            "booking_reference": reservation.booking_reference,
            "customer_id": user.id,
            "customer_name": user.full_name,
            "amount": _decimal_value(payment.amount),
            "currency": payment.currency,
            "status": _enum_value(payment.status),
            "created_at": payment.created_at.isoformat(),
        }
        for payment, reservation, user in rows
    ]


def get_report_data(
    db: Session,
    report_type: str,
    start_date: date,
    end_date: date,
):
    _validate_dates(start_date, end_date)

    if report_type not in REPORT_TYPES:
        raise ValueError(
            "Unsupported report type. Choose bookings, revenue, "
            "occupancy, customers, hotels, or payments."
        )

    report_functions = {
        "bookings": get_booking_report,
        "revenue": get_revenue_report,
        "occupancy": get_occupancy_report,
        "customers": get_customer_report,
        "hotels": get_hotel_report,
        "payments": get_payment_report,
    }

    return report_functions[report_type](
        db,
        start_date,
        end_date,
    )
