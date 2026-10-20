
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.reservation import Reservation, ReservationStatus
from app.models.payment import Payment, PaymentStatus
from app.models.room import Room
from app.models.hotel import Hotel
from app.schemas.customer_analytics import (
    CustomerMetric,
    PopularDestination,
    CustomerRetentionSummary,
    CustomerAnalyticsResponse,
)


ELIGIBLE_STATUSES = (
    ReservationStatus.CONFIRMED,
    ReservationStatus.COMPLETED,
)

ZERO = Decimal("0.00")


def _get_customer_ids(
    db: Session,
    start_date: date,
    end_date: date,
) -> set[int]:
    """Get customers with eligible bookings created during a date range."""
    start_datetime = datetime.combine(start_date, time.min)
    end_datetime = datetime.combine(
        end_date + timedelta(days=1),
        time.min,
    )

    results = (
        db.query(distinct(Reservation.customer_id))
        .join(User, User.id == Reservation.customer_id)
        .filter(
            User.role == UserRole.CUSTOMER,
            Reservation.status.in_(ELIGIBLE_STATUSES),
            Reservation.created_at >= start_datetime,
            Reservation.created_at < end_datetime,
        )
        .all()
    )

    return {row[0] for row in results}


def get_customer_analytics(
    db: Session,
    start_date: date,
    end_date: date,
) -> CustomerAnalyticsResponse:
    """Calculate booking frequency, spending, repeat customers,
    popular destinations, and customer retention.
    """
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")

    start_datetime = datetime.combine(start_date, time.min)
    end_datetime = datetime.combine(
        end_date + timedelta(days=1),
        time.min,
    )

    # Fetch eligible bookings created during the requested period.
    booking_rows = (
        db.query(Reservation, User, Hotel)
        .join(User, User.id == Reservation.customer_id)
        .join(Room, Room.id == Reservation.room_id)
        .join(Hotel, Hotel.id == Room.hotel_id)
        .filter(
            User.role == UserRole.CUSTOMER,
            Reservation.status.in_(ELIGIBLE_STATUSES),
            Reservation.created_at >= start_datetime,
            Reservation.created_at < end_datetime,
        )
        .all()
    )

    customer_bookings = {}
    destination_bookings = {}
    reservation_ids = []

    for reservation, user, hotel in booking_rows:
        customer_id = user.id

        if customer_id not in customer_bookings:
            customer_bookings[customer_id] = {
                "name": user.full_name,
                "booking_count": 0,
                "reservation_ids": [],
                "total_spending": ZERO,
            }

        customer_bookings[customer_id]["booking_count"] += 1
        customer_bookings[customer_id]["reservation_ids"].append(
            reservation.id
        )
        reservation_ids.append(reservation.id)

        destination_key = (
            hotel.city or "Unknown",
            hotel.country or "Unknown",
        )

        if destination_key not in destination_bookings:
            destination_bookings[destination_key] = {
                "booking_count": 0,
                "customers": set(),
            }

        destination_bookings[destination_key]["booking_count"] += 1
        destination_bookings[destination_key]["customers"].add(
            customer_id
        )

    # Sum successful payments for the bookings in this period.
    if reservation_ids:
        payment_rows = (
            db.query(
                Payment.reservation_id,
                func.sum(Payment.amount),
            )
            .filter(
                Payment.reservation_id.in_(reservation_ids),
                Payment.status == PaymentStatus.SUCCEEDED,
            )
            .group_by(Payment.reservation_id)
            .all()
        )

        spending_by_reservation = {
            reservation_id: Decimal(str(amount or ZERO))
            for reservation_id, amount in payment_rows
        }

        for customer_data in customer_bookings.values():
            customer_data["total_spending"] = sum(
                (
                    spending_by_reservation.get(
                        reservation_id, ZERO
                    )
                    for reservation_id in customer_data[
                        "reservation_ids"
                    ]
                ),
                ZERO,
            )

    customers = []

    for customer_id, data in customer_bookings.items():
        booking_frequency = data["booking_count"]
        total_spending = data["total_spending"]

        average_spending = (
            total_spending / booking_frequency
            if booking_frequency
            else ZERO
        )

        customers.append(
            CustomerMetric(
                customer_id=customer_id,
                customer_name=data["name"],
                booking_frequency=booking_frequency,
                total_spending=total_spending,
                average_spending=average_spending,
                is_repeat_customer=booking_frequency > 1,
            )
        )

    customers.sort(
        key=lambda customer: customer.total_spending,
        reverse=True,
    )

    popular_destinations = [
        PopularDestination(
            city=city,
            country=country,
            booking_count=data["booking_count"],
            unique_customers=len(data["customers"]),
        )
        for (city, country), data in destination_bookings.items()
    ]

    popular_destinations.sort(
        key=lambda destination: destination.booking_count,
        reverse=True,
    )

    # Compare the requested period with the immediately preceding
    # period of the same length to calculate customer retention.
    period_length = (end_date - start_date).days + 1
    previous_end_date = start_date - timedelta(days=1)
    previous_start_date = previous_end_date - timedelta(
        days=period_length - 1
    )

    previous_customer_ids = _get_customer_ids(
        db,
        previous_start_date,
        previous_end_date,
    )

    current_customer_ids = set(customer_bookings.keys())
    retained_customer_ids = (
        previous_customer_ids & current_customer_ids
    )

    retention_rate = (
        len(retained_customer_ids) / len(previous_customer_ids) * 100
        if previous_customer_ids
        else 0.0
    )

    retention = CustomerRetentionSummary(
        period_start=start_date,
        period_end=end_date,
        total_customers=len(previous_customer_ids),
        repeat_customers=len(retained_customer_ids),
        retention_rate=round(retention_rate, 2),
    )

    repeat_customer_count = sum(
        1
        for customer in customers
        if customer.is_repeat_customer
    )

    return CustomerAnalyticsResponse(
        period_start=start_date,
        period_end=end_date,
        total_customers=len(current_customer_ids),
        total_bookings=len(booking_rows),
        repeat_customers=repeat_customer_count,
        customers=customers,
        popular_destinations=popular_destinations,
        retention=retention,
    )
