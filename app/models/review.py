
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class HotelReview(Base):
    __tablename__ = "hotel_reviews"

    __table_args__ = (
        CheckConstraint(
            "rating >= 1 AND rating <= 5",
            name="ck_hotel_review_rating_range",
        ),
        UniqueConstraint(
            "reservation_id",
            name="uq_hotel_review_reservation",
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

    hotel_id: Mapped[int] = mapped_column(
        ForeignKey("hotels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    rating: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_reported: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    report_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_hidden: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
