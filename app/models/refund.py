
import enum
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
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


class RefundStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class Refund(Base):
    __tablename__ = "refunds"

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_refund_amount_positive",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    reservation_id: Mapped[int] = mapped_column(
        ForeignKey("reservations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="inr",
    )

    status: Mapped[RefundStatus] = mapped_column(
        Enum(RefundStatus, name="refund_status"),
        nullable=False,
        default=RefundStatus.PENDING,
        index=True,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )

    review_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    stripe_refund_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
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