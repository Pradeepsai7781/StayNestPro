import enum
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class PayoutStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PAID = "PAID"
    FAILED = "FAILED"


class ReconciliationStatus(str, enum.Enum):
    MATCHED = "MATCHED"
    MISMATCHED = "MISMATCHED"
    NOT_FOUND = "NOT_FOUND"


class FinancialRecord(Base):
    __tablename__ = "financial_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False, unique=True, index=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotels.id", ondelete="RESTRICT"), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="inr")
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    commission_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    commission_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    hotel_earnings: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class Settlement(Base):
    __tablename__ = "settlements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotels.id", ondelete="RESTRICT"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="inr")
    status: Mapped[PayoutStatus] = mapped_column(Enum(PayoutStatus, name="payout_status"), nullable=False, default=PayoutStatus.PENDING, index=True)
    provider_payout_reference: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class PaymentReconciliation(Base):
    __tablename__ = "payment_reconciliations"
    __table_args__ = (UniqueConstraint("provider_transaction_id", name="uq_reconciliation_provider_transaction"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    provider_transaction_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id", ondelete="RESTRICT"), nullable=True, index=True)
    provider_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    local_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    provider_status: Mapped[str] = mapped_column(String(50), nullable=False)
    local_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[ReconciliationStatus] = mapped_column(Enum(ReconciliationStatus, name="reconciliation_status"), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
