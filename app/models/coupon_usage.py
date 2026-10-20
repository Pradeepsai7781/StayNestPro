
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CouponUsage(Base):
    __tablename__ = "coupon_usages"

    __table_args__ = (
        UniqueConstraint(
            "coupon_id",
            "user_id",
            name="uq_coupon_usage_coupon_user",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    coupon_id: Mapped[int] = mapped_column(
        ForeignKey("coupons.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    reservation_id: Mapped[int | None] = mapped_column(
        ForeignKey("reservations.id", ondelete="RESTRICT"),
        nullable=True,
    )

    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
