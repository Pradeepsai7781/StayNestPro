
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class RevenueBreakdown(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period_start: date
    period_end: date
    booking_revenue: Decimal
    service_revenue: Decimal
    total_revenue: Decimal
    total_refunds: Decimal
    net_revenue: Decimal
    successful_booking_count: int
    average_booking_value: Decimal


class RevenueAnalyticsResponse(BaseModel):
    daily: list[RevenueBreakdown]
    monthly: list[RevenueBreakdown]
