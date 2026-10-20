
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class RoomStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"
    MAINTENANCE = "MAINTENANCE"
    INACTIVE = "INACTIVE"
    CLEAN = "CLEAN"
    DIRTY = "DIRTY"
    CLEANING = "CLEANING"
    INSPECTION = "INSPECTION"


class Room(Base):
    __tablename__ = "rooms"

    __table_args__ = (
        UniqueConstraint(
            "hotel_id",
            "room_number",
            name="uq_room_hotel_room_number",
        ),
        CheckConstraint(
            "capacity >= 1",
            name="ck_room_capacity_positive",
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

    room_type_id: Mapped[int] = mapped_column(
        ForeignKey("room_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    room_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[RoomStatus] = mapped_column(
        Enum(RoomStatus, name="room_status"),
        default=RoomStatus.AVAILABLE,
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
