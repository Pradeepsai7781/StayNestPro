
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class HotelImageCategory(str, enum.Enum):
    EXTERIOR = "EXTERIOR"
    ROOM = "ROOM"
    BATHROOM = "BATHROOM"
    DINING = "DINING"
    AMENITIES = "AMENITIES"
    OTHER = "OTHER"


class HotelImage(Base):
    __tablename__ = "hotel_images"

    __table_args__ = (
        CheckConstraint(
            "display_order >= 0",
            name="ck_hotel_image_display_order_nonnegative",
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

    image_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    caption: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    category: Mapped[HotelImageCategory] = mapped_column(
        Enum(HotelImageCategory, name="hotel_image_category"),
        default=HotelImageCategory.OTHER,
        nullable=False,
    )

    display_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
