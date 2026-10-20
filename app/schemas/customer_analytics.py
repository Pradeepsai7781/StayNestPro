
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CustomerMetric(BaseModel):
    customer_id: int
    customer_name: str
    booking_frequency: int
    total_spending: Decimal
    average_spending: Decimal
    is_repeat_customer: bool


class PopularDestination(BaseModel):
    city: str
    country: str
    booking_count: int
    unique_customers: int


class CustomerRetentionSummary(BaseModel):
    period_start: date
    period_end: date
    total_customers: int
    repeat_customers: int
    retention_rate: float


class CustomerAnalyticsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period_start: date
    period_end: date
    total_customers: int
    total_bookings: int
    repeat_customers: int
    customers: list[CustomerMetric]
    popular_destinations: list[PopularDestination]
    retention: CustomerRetentionSummary
