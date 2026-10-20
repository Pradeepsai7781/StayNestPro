
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.notification import Notification
from app.models.reservation import Reservation, ReservationStatus


def create_reservation_reminders(
    db: Session,
    reminder_date: date | None = None,
) -> int:
    """
    Create check-in and check-out reminders for confirmed reservations.

    By default, reminders are generated for tomorrow.
    A specific date can be supplied for testing.

    Existing reminders are checked to prevent duplicates.
    """
    if reminder_date is None:
        reminder_date = date.today() + timedelta(days=1)

    created_count = 0

    reservations = (
        db.query(Reservation)
        .filter(
            Reservation.status == ReservationStatus.CONFIRMED,
        )
        .all()
    )

    for reservation in reservations:
        reminders = []

        if reservation.check_in == reminder_date:
            reminders.append(
                {
                    "type": "check_in_reminder",
                    "title": "Check-in reminder",
                    "message": (
                        f"Your check-in for reservation "
                        f"#{reservation.id} is tomorrow, "
                        f"{reservation.check_in}."
                    ),
                }
            )

        if reservation.check_out == reminder_date:
            reminders.append(
                {
                    "type": "check_out_reminder",
                    "title": "Check-out reminder",
                    "message": (
                        f"Your check-out for reservation "
                        f"#{reservation.id} is tomorrow, "
                        f"{reservation.check_out}."
                    ),
                }
            )

        for reminder in reminders:
            existing = (
                db.query(Notification.id)
                .filter(
                    Notification.user_id == reservation.customer_id,
                    Notification.related_reservation_id == reservation.id,
                    Notification.notification_type == reminder["type"],
                )
                .first()
            )

            if existing is not None:
                continue

            db.add(
                Notification(
                    user_id=reservation.customer_id,
                    title=reminder["title"],
                    message=reminder["message"],
                    notification_type=reminder["type"],
                    related_reservation_id=reservation.id,
                    metadata_json={
                        "reservation_id": reservation.id,
                        "check_in": reservation.check_in.isoformat(),
                        "check_out": reservation.check_out.isoformat(),
                    },
                )
            )

            created_count += 1

    if created_count > 0:
        db.commit()

    return created_count


def run_reservation_reminder_job() -> None:
    """Run the reminder task with its own database session."""
    db = SessionLocal()

    try:
        count = create_reservation_reminders(db)
        print(
            f"Reservation reminder job completed. Created: {count}"
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()