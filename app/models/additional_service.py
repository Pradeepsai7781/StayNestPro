
import enum
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
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


class AdditionalServiceCategory(str, enum.Enum):
    LAUNDRY = "LAUNDRY"
    SPA = "SPA"
    RESTAURANT = "RESTAURANT"
    AIRPORT_PICKUP = "AIRPORT_PICKUP"
    EXTRA_BED = "EXTRA_BED"


class ServiceRequestStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"
    CONFIRMED = "CONFIRMED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class AdditionalService(Base):
    __tablename__ = "additional_services"

    __table_args__ = (
        CheckConstraint(
            "price >= 0",
            name="ck_additional_service_price_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    category: Mapped[AdditionalServiceCategory] = mapped_column(
        Enum(
            AdditionalServiceCategory,
            name="additional_service_category",
        ),
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
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


class ServiceRequest(Base):
    __tablename__ = "service_requests"

    __table_args__ = (
        CheckConstraint(
            "quantity >= 1",
            name="ck_service_request_quantity_positive",
        ),
        CheckConstraint(
            "unit_price >= 0",
            name="ck_service_request_unit_price_nonnegative",
        ),
        CheckConstraint(
            "total_charge >= 0",
            name="ck_service_request_total_charge_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    reservation_id: Mapped[int] = mapped_column(
        ForeignKey("reservations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    service_id: Mapped[int] = mapped_column(
        ForeignKey("additional_services.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    requested_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    total_charge: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    status: Mapped[ServiceRequestStatus] = mapped_column(
        Enum(
            ServiceRequestStatus,
            name="service_request_status",
        ),
        default=ServiceRequestStatus.REQUESTED,
        nullable=False,
        index=True,
    )

    special_instructions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    requested_at: Mapped[datetime] = mapped_column(
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

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
