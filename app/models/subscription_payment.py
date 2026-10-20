
from datetime import datetime, timezone
import enum

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SubscriptionPaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class SubscriptionPayment(Base):
    __tablename__ = "subscription_payments"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    hotel_subscription_id: Mapped[int] = mapped_column(
        ForeignKey("hotel_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    stripe_payment_intent_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
    )

    stripe_invoice_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    amount: Mapped[float] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        default="usd",
        nullable=False,
    )

    status: Mapped[SubscriptionPaymentStatus] = mapped_column(
        Enum(SubscriptionPaymentStatus, name="subscription_payment_status"),
        default=SubscriptionPaymentStatus.PENDING,
        nullable=False,
        index=True,
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
