
import enum
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class RoomTypeCategory(str, enum.Enum):
    SINGLE = "SINGLE"
    DOUBLE = "DOUBLE"
    DELUXE = "DELUXE"
    SUITE = "SUITE"
    FAMILY = "FAMILY"


class RoomType(Base):
    __tablename__ = "room_types"

    __table_args__ = (
        UniqueConstraint(
            "hotel_id",
            "name",
            name="uq_room_type_hotel_name",
        ),
        CheckConstraint(
            "price_per_night > 0",
            name="ck_room_type_price_positive",
        ),
        CheckConstraint(
            "capacity >= 1",
            name="ck_room_type_capacity_positive",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    hotel_id: Mapped[int] = mapped_column(
        ForeignKey("hotels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[RoomTypeCategory] = mapped_column(
        Enum(RoomTypeCategory, name="room_type_category"),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    price_per_night: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    amenities: Mapped[list] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    images: Mapped[list] = mapped_column(
        JSON,
        default=list,
        nullable=False,
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
