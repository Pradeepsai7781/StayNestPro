
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Hotel,
    Reservation,
    ReservationStatus,
    Room,
    RoomStatus,
    Payment,
    PaymentStatus,
    HotelReview,
)
from app.schemas.hotel_owner_dashboard import (
    HotelDashboardSummary,
    HotelOwnerDashboardResponse,
    TodayBooking,
)


ZERO = Decimal("0.00")

UNAVAILABLE_ROOM_STATUSES = {
    RoomStatus.MAINTENANCE,
    RoomStatus.INACTIVE,
    RoomStatus.DIRTY,
    RoomStatus.CLEANING,
    RoomStatus.INSPECTION,
}


def get_hotel_owner_dashboard(
    db: Session,
    owner_id: int,
    dashboard_date: date | None = None,
) -> HotelOwnerDashboardResponse:
    if dashboard_date is None:
        dashboard_date = date.today()

    start_datetime = datetime.combine(dashboard_date, time.min)
    end_datetime = start_datetime + timedelta(days=1)

    # Only hotels owned by the authenticated owner are included.
    hotels = (
        db.query(Hotel)
        .filter(Hotel.owner_id == owner_id)
        .order_by(Hotel.id)
        .all()
    )

    hotel_ids = [hotel.id for hotel in hotels]

    if not hotel_ids:
        return HotelOwnerDashboardResponse(
            dashboard_date=dashboard_date,
            total_hotels=0,
            today_bookings_count=0,
            current_guests=0,
            total_rooms=0,
            occupied_rooms=0,
            available_rooms=0,
            total_revenue=ZERO,
            occupancy_rate=0.0,
            average_review_rating=None,
            total_reviews=0,
            today_bookings=[],
            hotels=[],
        )

    hotel_names = {hotel.id: hotel.name for hotel in hotels}

    # Today's check-ins.
    booking_rows = (
        db.query(Reservation, Room)
        .join(Room, Reservation.room_id == Room.id)
        .filter(
            Room.hotel_id.in_(hotel_ids),
            Reservation.check_in == dashboard_date,
            Reservation.status == ReservationStatus.CONFIRMED,
        )
        .order_by(Reservation.check_in, Reservation.id)
        .all()
    )

    today_bookings = [
        TodayBooking(
            reservation_id=reservation.id,
            booking_reference=reservation.booking_reference,
            hotel_id=room.hotel_id,
            hotel_name=hotel_names[room.hotel_id],
            room_id=room.id,
            customer_id=reservation.customer_id,
            check_in=reservation.check_in,
            check_out=reservation.check_out,
            guest_count=reservation.guest_count,
            total_price=reservation.total_price,
            status=reservation.status.value,
        )
        for reservation, room in booking_rows
    ]

    # Current rooms and guests.
    room_rows = (
        db.query(Room)
        .filter(Room.hotel_id.in_(hotel_ids))
        .all()
    )

    rooms_by_hotel = {hotel_id: [] for hotel_id in hotel_ids}

    for room in room_rows:
        rooms_by_hotel[room.hotel_id].append(room)

    active_reservations = (
        db.query(Reservation, Room)
        .join(Room, Reservation.room_id == Room.id)
        .filter(
            Room.hotel_id.in_(hotel_ids),
            Reservation.status == ReservationStatus.CONFIRMED,
            Reservation.check_in <= dashboard_date,
            Reservation.check_out > dashboard_date,
        )
        .all()
    )

    guests_by_hotel = {hotel_id: 0 for hotel_id in hotel_ids}
    occupied_room_ids_by_hotel = {
        hotel_id: set() for hotel_id in hotel_ids
    }

    for reservation, room in active_reservations:
        guests_by_hotel[room.hotel_id] += reservation.guest_count
        occupied_room_ids_by_hotel[room.hotel_id].add(room.id)

    # Revenue from successful payments linked to reservations at these hotels.
    revenue_rows = (
        db.query(
            Room.hotel_id,
            func.sum(Payment.amount),
        )
        .join(Reservation, Payment.reservation_id == Reservation.id)
        .join(Room, Reservation.room_id == Room.id)
        .filter(
            Room.hotel_id.in_(hotel_ids),
            Payment.status == PaymentStatus.SUCCEEDED,
            Payment.created_at >= start_datetime,
            Payment.created_at < end_datetime,
        )
        .group_by(Room.hotel_id)
        .all()
    )

    revenue_by_hotel = {
        hotel_id: Decimal(str(amount or ZERO))
        for hotel_id, amount in revenue_rows
    }

    # Review summaries exclude hidden and reported reviews.
    review_rows = (
        db.query(
            HotelReview.hotel_id,
            func.avg(HotelReview.rating),
            func.count(HotelReview.id),
        )
        .filter(
            HotelReview.hotel_id.in_(hotel_ids),
            HotelReview.is_hidden.is_(False),
            HotelReview.is_reported.is_(False),
        )
        .group_by(HotelReview.hotel_id)
        .all()
    )

    reviews_by_hotel = {
        hotel_id: (float(avg_rating), int(review_count))
        for hotel_id, avg_rating, review_count in review_rows
    }

    hotel_summaries = []

    for hotel in hotels:
        hotel_rooms = rooms_by_hotel[hotel.id]
        total_rooms = len(hotel_rooms)
        occupied_room_ids = occupied_room_ids_by_hotel[hotel.id]

        occupied_rooms = len(occupied_room_ids)

        available_rooms = sum(
            1
            for room in hotel_rooms
            if room.status not in UNAVAILABLE_ROOM_STATUSES
            and room.id not in occupied_room_ids
        )

        occupancy_rate = (
            occupied_rooms / total_rooms * 100
            if total_rooms
            else 0.0
        )

        hotel_today_bookings = sum(
            1
            for reservation, room in booking_rows
            if room.hotel_id == hotel.id
        )

        average_rating, review_count = reviews_by_hotel.get(
            hotel.id,
            (None, 0),
        )

        hotel_summaries.append(
            HotelDashboardSummary(
                hotel_id=hotel.id,
                hotel_name=hotel.name,
                total_rooms=total_rooms,
                occupied_rooms=occupied_rooms,
                available_rooms=available_rooms,
                current_guests=guests_by_hotel[hotel.id],
                today_bookings=hotel_today_bookings,
                revenue=revenue_by_hotel.get(hotel.id, ZERO),
                occupancy_rate=round(occupancy_rate, 2),
                average_review_rating=average_rating,
                total_reviews=review_count,
            )
        )

    total_rooms = sum(item.total_rooms for item in hotel_summaries)
    occupied_rooms = sum(item.occupied_rooms for item in hotel_summaries)
    available_rooms = sum(item.available_rooms for item in hotel_summaries)
    current_guests = sum(item.current_guests for item in hotel_summaries)
    total_revenue = sum(
        (item.revenue for item in hotel_summaries),
        ZERO,
    )
    total_reviews = sum(item.total_reviews for item in hotel_summaries)

    # Overall review average is weighted by each hotel's review count.
    weighted_rating_total = sum(
        (
            (item.average_review_rating or 0.0) * item.total_reviews
            for item in hotel_summaries
        ),
        0.0,
    )

    average_review_rating = (
        weighted_rating_total / total_reviews
        if total_reviews
        else None
    )

    overall_occupancy_rate = (
        occupied_rooms / total_rooms * 100
        if total_rooms
        else 0.0
    )

    return HotelOwnerDashboardResponse(
        dashboard_date=dashboard_date,
        total_hotels=len(hotels),
        today_bookings_count=len(today_bookings),
        current_guests=current_guests,
        total_rooms=total_rooms,
        occupied_rooms=occupied_rooms,
        available_rooms=available_rooms,
        total_revenue=total_revenue,
        occupancy_rate=round(overall_occupancy_rate, 2),
        average_review_rating=(
            round(average_review_rating, 2)
            if average_review_rating is not None
            else None
        ),
        total_reviews=total_reviews,
        today_bookings=today_bookings,
        hotels=hotel_summaries,
    )
