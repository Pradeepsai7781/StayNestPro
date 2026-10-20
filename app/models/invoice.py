
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Invoice(Base):
    __tablename__ = "invoices"

    __table_args__ = (
        CheckConstraint(
            "subtotal >= 0",
            name="ck_invoice_subtotal_nonnegative",
        ),
        CheckConstraint(
            "tax_amount >= 0",
            name="ck_invoice_tax_nonnegative",
        ),
        CheckConstraint(
            "total_amount >= 0",
            name="ck_invoice_total_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    invoice_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
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

    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )

    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="inr",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
