
import enum
import secrets
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def generate_booking_reference() -> str:
    return f"SN-{secrets.token_hex(6).upper()}"


class ReservationStatus(str, enum.Enum):
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class Reservation(Base):
    __tablename__ = "reservations"

    __table_args__ = (
        CheckConstraint(
            "check_out > check_in",
            name="ck_reservation_checkout_after_checkin",
        ),
        CheckConstraint(
            "guest_count >= 1",
            name="ck_reservation_guest_count_positive",
        ),
        CheckConstraint(
            "total_price >= 0",
            name="ck_reservation_total_price_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    room_id: Mapped[int] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    check_in: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    check_out: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    guest_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    booking_reference: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
        index=True,
        default=generate_booking_reference,
    )

    total_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus, name="reservation_status"),
        default=ReservationStatus.CONFIRMED,
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
