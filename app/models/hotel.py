
import enum
from datetime import datetime, timezone, time

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    JSON,
    Time,
    Float,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class HotelStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"


class PropertyType(str, enum.Enum):
    HOTEL = "HOTEL"
    RESORT = "RESORT"
    GUEST_HOUSE = "GUEST_HOUSE"
    HOSTEL = "HOSTEL"
    HOMESTAY = "HOMESTAY"
    VILLA = "VILLA"


class Hotel(Base):
    __tablename__ = "hotels"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    phone_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    address: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    state: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    postal_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    country: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    latitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    longitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    property_type: Mapped[PropertyType] = mapped_column(
        Enum(PropertyType, name="property_type"),
        default=PropertyType.HOTEL,
        nullable=False,
        index=True,
    )

    # Placeholder rating until a verified review/rating system exists.
    rating: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    policies: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    check_in_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )

    check_out_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )

    check_in_rules: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[HotelStatus] = mapped_column(
        Enum(HotelStatus, name="hotel_status"),
        default=HotelStatus.PENDING,
        nullable=False,
    )

    # Reported-property moderation
    is_reported: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    report_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Administrator decision details
    decision_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    decision_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    decision_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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
