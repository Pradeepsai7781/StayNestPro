
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.room_service import RoomServiceOrderStatus


# ---------------------------------------------------------
# MENU ITEM SCHEMAS
# ---------------------------------------------------------

class MenuItemCreate(BaseModel):
    hotel_id: int = Field(gt=0)
    name: str = Field(min_length=2, max_length=120)
    description: str | None = None
    category: str = Field(min_length=2, max_length=80)
    price: Decimal = Field(
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
    is_available: bool = True


class MenuItemUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=120,
    )
    description: str | None = None
    category: str | None = Field(
        default=None,
        min_length=2,
        max_length=80,
    )
    price: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
    is_available: bool | None = None


class MenuItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    name: str
    description: str | None
    category: str
    price: Decimal
    is_available: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------
# ORDER ITEM SCHEMAS
# ---------------------------------------------------------

class RoomServiceOrderItemCreate(BaseModel):
    menu_item_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=100)


class RoomServiceOrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    menu_item_id: int
    item_name: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal


# ---------------------------------------------------------
# ROOM SERVICE ORDER SCHEMAS
# ---------------------------------------------------------

class RoomServiceOrderCreate(BaseModel):
    reservation_id: int = Field(gt=0)
    items: list[RoomServiceOrderItemCreate] = Field(
        min_length=1,
        max_length=50,
    )
    service_charge: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
    special_instructions: str | None = Field(
        default=None,
        max_length=1000,
    )


class RoomServiceOrderStatusUpdate(BaseModel):
    status: RoomServiceOrderStatus


class RoomServiceOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reservation_id: int
    hotel_id: int
    ordered_by: int
    subtotal: Decimal
    service_charge: Decimal
    total_amount: Decimal
    status: RoomServiceOrderStatus
    special_instructions: str | None
    ordered_at: datetime
    updated_at: datetime
    delivered_at: datetime | None
    items: list[RoomServiceOrderItemResponse]


# ---------------------------------------------------------
# ORDER HISTORY SCHEMA
# ---------------------------------------------------------

class RoomServiceOrderHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    status: RoomServiceOrderStatus
    notes: str | None
    changed_by: int
    changed_at: datetime
