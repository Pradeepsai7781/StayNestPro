
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.room import Room, RoomStatus
from app.models.reservation import Reservation, ReservationStatus


UNAVAILABLE_ROOM_STATUSES = {
    RoomStatus.MAINTENANCE,
    RoomStatus.CLEANING,
    RoomStatus.INSPECTION,
}


def get_occupancy_summary(
    db: Session,
    start_date: date,
    end_date: date,
    hotel_id: int | None = None,
):
    if start_date > end_date:
        raise ValueError("start_date cannot be after end_date")

    room_query = db.query(Room)

    if hotel_id is not None:
        room_query = room_query.filter(Room.hotel_id == hotel_id)

    rooms = room_query.all()
    room_ids = [room.id for room in rooms]
    total_rooms = len(rooms)

    unavailable_room_ids = {
        room.id
        for room in rooms
        if room.status in UNAVAILABLE_ROOM_STATUSES
    }

    daily_summaries = []
    current_date = start_date

    while current_date <= end_date:
        next_date = current_date + timedelta(days=1)

        if room_ids:
            reservations = (
                db.query(Reservation)
                .filter(
                    Reservation.room_id.in_(room_ids),
                    Reservation.status == ReservationStatus.CONFIRMED,
                    Reservation.check_in < next_date,
                    Reservation.check_out > current_date,
                )
                .all()
            )
        else:
            reservations = []

        # Count each room only once per day, even if bad data
        # contains overlapping reservations for that room.
        occupied_room_ids = {
            reservation.room_id for reservation in reservations
        }

        # A room under maintenance, cleaning, or inspection
        # is not counted as occupied or available.
        occupied_room_ids -= unavailable_room_ids

        occupied_rooms = len(occupied_room_ids)
        unavailable_rooms = len(unavailable_room_ids)
        available_rooms = max(
            total_rooms - occupied_rooms - unavailable_rooms,
            0,
        )

        occupancy_rate = (
            occupied_rooms / total_rooms * 100
            if total_rooms
            else 0.0
        )

        daily_summaries.append(
            {
                "date": current_date,
                "total_rooms": total_rooms,
                "occupied_rooms": occupied_rooms,
                "available_rooms": available_rooms,
                "unavailable_rooms": unavailable_rooms,
                "occupancy_rate": round(occupancy_rate, 2),
                "booking_count": len(reservations),
            }
        )

        current_date = next_date

    # Find distinct reservations overlapping the entire period.
    if room_ids:
        total_bookings = (
            db.query(Reservation.id)
            .filter(
                Reservation.room_id.in_(room_ids),
                Reservation.status == ReservationStatus.CONFIRMED,
                Reservation.check_in < end_date + timedelta(days=1),
                Reservation.check_out > start_date,
            )
            .distinct()
            .count()
        )
    else:
        total_bookings = 0

    # Range-level room counts represent accumulated room-days.
    occupied_room_days = sum(
        item["occupied_rooms"] for item in daily_summaries
    )
    available_room_days = sum(
        item["available_rooms"] for item in daily_summaries
    )
    unavailable_room_days = sum(
        item["unavailable_rooms"] for item in daily_summaries
    )

    total_room_days = total_rooms * len(daily_summaries)

    overall_occupancy_rate = (
        occupied_room_days / total_room_days * 100
        if total_room_days
        else 0.0
    )

    # Peak periods are dates with the highest occupancy rate.
    highest_occupancy_rate = max(
        (item["occupancy_rate"] for item in daily_summaries),
        default=0.0,
    )

    peak_booking_dates = (
        [
            item["date"]
            for item in daily_summaries
            if item["occupancy_rate"] == highest_occupancy_rate
        ]
        if highest_occupancy_rate > 0
        else []
    )

    return {
        "period_start": start_date,
        "period_end": end_date,
        "total_rooms": total_rooms,
        "occupied_rooms": occupied_room_days,
        "available_rooms": available_room_days,
        "unavailable_rooms": unavailable_room_days,
        "occupancy_rate": round(overall_occupancy_rate, 2),
        "total_bookings": total_bookings,
        "peak_booking_dates": peak_booking_dates,
        "daily_summaries": daily_summaries,
    }
