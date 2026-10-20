
import enum
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CouponType(str, enum.Enum):
    FIXED = "FIXED"
    PERCENTAGE = "PERCENTAGE"


class Coupon(Base):
    __tablename__ = "coupons"

    __table_args__ = (
        CheckConstraint(
            "discount_value > 0",
            name="ck_coupon_discount_value_positive",
        ),
        CheckConstraint(
            "min_booking_amount >= 0",
            name="ck_coupon_min_booking_nonnegative",
        ),
        CheckConstraint(
            "usage_limit IS NULL OR usage_limit > 0",
            name="ck_coupon_usage_limit_positive",
        ),
        CheckConstraint(
            "used_count >= 0",
            name="ck_coupon_used_count_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )

    code: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    coupon_type: Mapped[CouponType] = mapped_column(
        Enum(CouponType, name="coupon_type"),
        nullable=False,
    )

    discount_value: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )

    min_booking_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )

    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    usage_limit: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    used_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    is_seasonal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    is_early_booking: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
