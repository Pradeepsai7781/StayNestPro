
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class GuestIdType(str, enum.Enum):
    PASSPORT = "PASSPORT"
    DRIVING_LICENSE = "DRIVING_LICENSE"
    NATIONAL_ID = "NATIONAL_ID"
    OTHER = "OTHER"


class Guest(Base):
    __tablename__ = "guests"

    __table_args__ = (
        CheckConstraint(
            "age IS NULL OR age >= 0",
            name="ck_guest_age_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    reservation_id: Mapped[int] = mapped_column(
        ForeignKey("reservations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    age: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    id_type: Mapped[GuestIdType | None] = mapped_column(
        Enum(GuestIdType, name="guest_id_type"),
        nullable=True,
    )

    # Store a masked identifier or a reference to a secure verification
    # record, not an unnecessary full government ID number.
    id_number_masked: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    special_requests: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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
