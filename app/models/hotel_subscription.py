
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SubscriptionPlan(str, enum.Enum):
    FREE = "FREE"
    BASIC = "BASIC"
    PREMIUM = "PREMIUM"
    ENTERPRISE = "ENTERPRISE"


class BillingPeriod(str, enum.Enum):
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class HotelSubscription(Base):
    __tablename__ = "hotel_subscriptions"
    __table_args__ = (
        UniqueConstraint("hotel_id", name="uq_hotel_subscriptions_hotel_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    hotel_id: Mapped[int] = mapped_column(
        ForeignKey("hotels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    plan: Mapped[SubscriptionPlan] = mapped_column(
        Enum(SubscriptionPlan, name="subscription_plan"),
        default=SubscriptionPlan.FREE,
        nullable=False,
    )

    billing_period: Mapped[BillingPeriod] = mapped_column(
        Enum(BillingPeriod, name="subscription_billing_period"),
        default=BillingPeriod.MONTHLY,
        nullable=False,
    )

    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status"),
        default=SubscriptionStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
    )

    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
