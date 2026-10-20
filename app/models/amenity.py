
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Column,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


hotel_amenities = Table(
    "hotel_amenities",
    Base.metadata,
    Column(
        "hotel_id",
        Integer,
        ForeignKey("hotels.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "amenity_id",
        Integer,
        ForeignKey("amenities.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    UniqueConstraint(
        "hotel_id",
        "amenity_id",
        name="uq_hotel_amenity",
    ),
)


class Amenity(Base):
    __tablename__ = "amenities"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
