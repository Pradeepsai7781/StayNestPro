from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.payment import Payment, PaymentStatus
from app.models.refund import Refund, RefundStatus
from app.models.reservation import Reservation
from app.models.additional_service import ServiceRequest, ServiceRequestStatus
from app.models.room_service import RoomServiceOrder, RoomServiceOrderStatus

ZERO = Decimal("0.00")


def _utc_bounds(start_date: date, end_date: date):
    start = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(
        end_date + timedelta(days=1),
        time.min,
        tzinfo=timezone.utc,
    )
    return start, end


def get_revenue_for_period(
    db: Session,
    start_date: date,
    end_date: date,
):
    start, end = _utc_bounds(start_date, end_date)

    booking_query = (
        select(func.coalesce(func.sum(Payment.amount), 0))
        .join(Reservation, Reservation.id == Payment.reservation_id)
        .where(Payment.status == PaymentStatus.SUCCEEDED)
        .where(Payment.created_at >= start)
        .where(Payment.created_at < end)
    )
    booking_revenue = Decimal(
        str(db.execute(booking_query).scalar_one())
    )

    booking_count_query = (
        select(func.count(func.distinct(Payment.reservation_id)))
        .where(Payment.status == PaymentStatus.SUCCEEDED)
        .where(Payment.created_at >= start)
        .where(Payment.created_at < end)
    )
    booking_count = db.execute(booking_count_query).scalar_one()

    additional_service_query = (
        select(func.coalesce(func.sum(ServiceRequest.total_charge), 0))
        .where(ServiceRequest.status == ServiceRequestStatus.COMPLETED)
        .where(ServiceRequest.completed_at >= start)
        .where(ServiceRequest.completed_at < end)
    )
    additional_service_revenue = Decimal(
        str(db.execute(additional_service_query).scalar_one())
    )

    room_service_query = (
        select(func.coalesce(func.sum(RoomServiceOrder.total_amount), 0))
        .where(RoomServiceOrder.status == RoomServiceOrderStatus.DELIVERED)
        .where(RoomServiceOrder.delivered_at >= start)
        .where(RoomServiceOrder.delivered_at < end)
    )
    room_service_revenue = Decimal(
        str(db.execute(room_service_query).scalar_one())
    )

    service_revenue = (
        additional_service_revenue + room_service_revenue
    )

    refund_query = (
        select(func.coalesce(func.sum(Refund.amount), 0))
        .join(Payment, Payment.id == Refund.payment_id)
        .where(Refund.status == RefundStatus.SUCCEEDED)
        .where(Payment.status == PaymentStatus.SUCCEEDED)
        .where(Refund.updated_at >= start)
        .where(Refund.updated_at < end)
    )
    total_refunds = Decimal(
        str(db.execute(refund_query).scalar_one())
    )

    total_revenue = booking_revenue + service_revenue
    net_revenue = total_revenue - total_refunds

    average_booking_value = (
        booking_revenue / booking_count
        if booking_count
        else ZERO
    )

    return {
        "period_start": start_date,
        "period_end": end_date,
        "booking_revenue": booking_revenue,
        "service_revenue": service_revenue,
        "total_revenue": total_revenue,
        "total_refunds": total_refunds,
        "net_revenue": net_revenue,
        "successful_booking_count": booking_count,
        "average_booking_value": average_booking_value,
    }


def get_daily_revenue(
    db: Session,
    start_date: date,
    end_date: date,
):
    results = []
    current_date = start_date

    while current_date <= end_date:
        results.append(
            get_revenue_for_period(
                db,
                current_date,
                current_date,
            )
        )
        current_date += timedelta(days=1)

    return results


def get_monthly_revenue(
    db: Session,
    year: int,
    month: int,
):
    first_day = date(year, month, 1)

    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)

    last_day = next_month - timedelta(days=1)

    return get_revenue_for_period(
        db,
        first_day,
        last_day,
    )