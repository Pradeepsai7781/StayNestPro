
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class TodayBooking(BaseModel):
    reservation_id: int
    booking_reference: str
    hotel_id: int
    hotel_name: str
    room_id: int
    customer_id: int
    check_in: date
    check_out: date
    guest_count: int
    total_price: Decimal
    status: str


class HotelDashboardSummary(BaseModel):
    hotel_id: int
    hotel_name: str
    total_rooms: int
    occupied_rooms: int
    available_rooms: int
    current_guests: int
    today_bookings: int
    revenue: Decimal
    occupancy_rate: float
    average_review_rating: float | None
    total_reviews: int


class HotelOwnerDashboardResponse(BaseModel):
    dashboard_date: date
    total_hotels: int
    today_bookings_count: int
    current_guests: int
    total_rooms: int
    occupied_rooms: int
    available_rooms: int
    total_revenue: Decimal
    occupancy_rate: float
    average_review_rating: float | None
    total_reviews: int
    today_bookings: list[TodayBooking]
    hotels: list[HotelDashboardSummary]
