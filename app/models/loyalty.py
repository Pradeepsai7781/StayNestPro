
import enum
import secrets
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class LoyaltyEntryType(str, enum.Enum):
    BOOKING_REWARD = "BOOKING_REWARD"
    REDEMPTION = "REDEMPTION"
    REFERRAL_REWARD = "REFERRAL_REWARD"
    REFERRAL_BONUS = "REFERRAL_BONUS"


class LoyaltyAccount(Base):
    __tablename__ = "loyalty_accounts"

    __table_args__ = (
        CheckConstraint(
            "points_balance >= 0",
            name="ck_loyalty_points_balance_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    points_balance: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    membership_tier: Mapped[str] = mapped_column(
        String(20), nullable=False, default="BRONZE"
    )

    referral_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
        index=True,
        default=lambda: secrets.token_hex(5).upper(),
    )

    referred_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
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


class LoyaltyLedgerEntry(Base):
    __tablename__ = "loyalty_ledger"

    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            name="uq_loyalty_ledger_idempotency_key",
        ),
        CheckConstraint(
            "points != 0",
            name="ck_loyalty_ledger_points_nonzero",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    reservation_id: Mapped[int | None] = mapped_column(
        ForeignKey("reservations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    payment_id: Mapped[int | None] = mapped_column(
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    entry_type: Mapped[LoyaltyEntryType] = mapped_column(
        Enum(LoyaltyEntryType, name="loyalty_entry_type"),
        nullable=False,
    )

    points: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    monetary_value: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(150), nullable=False
    )

    description: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
