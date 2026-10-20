from datetime import date

from pydantic import BaseModel, ConfigDict


class DailyOccupancySummary(BaseModel):
    date: date
    total_rooms: int
    occupied_rooms: int
    available_rooms: int
    unavailable_rooms: int
    occupancy_rate: float
    booking_count: int


class OccupancySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period_start: date
    period_end: date
    total_rooms: int
    occupied_rooms: int
    available_rooms: int
    unavailable_rooms: int
    occupancy_rate: float
    total_bookings: int
    peak_booking_dates: list[date]
    daily_summaries: list[DailyOccupancySummary]