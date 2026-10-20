
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class CustomerDashboardResponse(BaseModel):
    upcoming_bookings: list[dict[str, Any]]
    booking_history: list[dict[str, Any]]
    hotel_wishlist: list[dict[str, Any]]
    room_wishlist: list[dict[str, Any]]
    payment_history: list[dict[str, Any]]
    notifications: list[dict[str, Any]]
    recommended_hotels: list[dict[str, Any]]


class CustomerBookingItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    customer_id: int
    check_in: date
    check_out: date
    guest_count: int
    booking_reference: str
    total_price: float
    status: str
    created_at: datetime
