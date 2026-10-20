
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class RoomServiceOrderStatus(str, enum.Enum):
    ORDERED = "ORDERED"
    PREPARING = "PREPARING"
    READY = "READY"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class MenuItem(Base):
    __tablename__ = "room_service_menu_items"

    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_menu_item_price_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    hotel_id: Mapped[int] = mapped_column(
        ForeignKey("hotels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_available: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
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


class RoomServiceOrder(Base):
    __tablename__ = "room_service_orders"

    __table_args__ = (
        CheckConstraint("subtotal >= 0", name="ck_room_service_subtotal"),
        CheckConstraint(
            "service_charge >= 0", name="ck_room_service_charge"
        ),
        CheckConstraint(
            "total_amount >= 0", name="ck_room_service_total"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reservation_id: Mapped[int] = mapped_column(
        ForeignKey("reservations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hotel_id: Mapped[int] = mapped_column(
        ForeignKey("hotels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordered_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    service_charge: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    status: Mapped[RoomServiceOrderStatus] = mapped_column(
        Enum(RoomServiceOrderStatus, name="room_service_order_status"),
        default=RoomServiceOrderStatus.ORDERED,
        nullable=False,
        index=True,
    )
    special_instructions: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    ordered_at: Mapped[datetime] = mapped_column(
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
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    items: Mapped[list["RoomServiceOrderItem"]] = relationship(
        "RoomServiceOrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class RoomServiceOrderItem(Base):
    __tablename__ = "room_service_order_items"

    __table_args__ = (
        CheckConstraint("quantity >= 1", name="ck_room_service_quantity"),
        CheckConstraint(
            "unit_price >= 0", name="ck_room_service_unit_price"
        ),
        CheckConstraint(
            "line_total >= 0", name="ck_room_service_line_total"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("room_service_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    menu_item_id: Mapped[int] = mapped_column(
        ForeignKey("room_service_menu_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    item_name: Mapped[str] = mapped_column(String(150), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )

    order: Mapped["RoomServiceOrder"] = relationship(
        "RoomServiceOrder",
        back_populates="items",
    )


class RoomServiceOrderHistory(Base):
    __tablename__ = "room_service_order_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("room_service_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[RoomServiceOrderStatus] = mapped_column(
        Enum(RoomServiceOrderStatus, name="room_service_order_status"),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
