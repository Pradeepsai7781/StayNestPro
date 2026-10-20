
from datetime import date, datetime

from pydantic import BaseModel


class AdminDashboardSummary(BaseModel):
    total_customers: int
    total_hotels: int
    total_rooms: int
    total_bookings: int
    platform_revenue: float
    active_reservations: int


class AdminDashboardResponse(BaseModel):
    summary: AdminDashboardSummary
    start_date: date | None = None
    end_date: date | None = None
    hotel_id: int | None = None
    status: str | None = None
    active_reservation_details: list[dict]
