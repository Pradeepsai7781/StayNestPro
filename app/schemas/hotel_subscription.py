
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.hotel_subscription import (
    BillingPeriod,
    SubscriptionPlan,
    SubscriptionStatus,
)


class HotelSubscriptionCreate(BaseModel):
    hotel_id: int
    plan: SubscriptionPlan = SubscriptionPlan.FREE
    billing_period: BillingPeriod = BillingPeriod.MONTHLY


class HotelSubscriptionUpdate(BaseModel):
    plan: SubscriptionPlan
    billing_period: BillingPeriod = BillingPeriod.MONTHLY


class HotelSubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    plan: SubscriptionPlan
    billing_period: BillingPeriod
    status: SubscriptionStatus
    started_at: datetime
    expires_at: datetime | None


class SubscriptionPlanBenefitsResponse(BaseModel):
    plan: SubscriptionPlan
    listing_limit: int | None
    analytics_access: bool
    description: str
