
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class PricingRuleType(str, enum.Enum):
    SEASONAL = "SEASONAL"
    WEEKEND = "WEEKEND"
    HOLIDAY = "HOLIDAY"
    PROMOTIONAL = "PROMOTIONAL"


class PricingAdjustmentType(str, enum.Enum):
    FIXED_PRICE = "FIXED_PRICE"
    PERCENTAGE = "PERCENTAGE"


class DynamicPricing(Base):
    __tablename__ = "dynamic_pricing"

    __table_args__ = (
        CheckConstraint(
            "end_date >= start_date",
            name="ck_dynamic_pricing_valid_dates",
        ),
        CheckConstraint(
            "adjustment_value >= 0",
            name="ck_dynamic_pricing_nonnegative_adjustment",
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

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    rule_type: Mapped[PricingRuleType] = mapped_column(
        Enum(PricingRuleType, name="pricing_rule_type"),
        nullable=False,
        index=True,
    )

    adjustment_type: Mapped[PricingAdjustmentType] = mapped_column(
        Enum(
            PricingAdjustmentType,
            name="pricing_adjustment_type",
        ),
        nullable=False,
    )

    adjustment_value: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    start_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    end_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
