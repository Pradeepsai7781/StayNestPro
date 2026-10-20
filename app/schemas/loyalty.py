
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class LoyaltyAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    points_balance: int
    membership_tier: str
    referral_code: str


class LoyaltyLedgerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reservation_id: int | None
    payment_id: int | None
    entry_type: str
    points: int
    monetary_value: Decimal | None
    description: str
    created_at: datetime


class LoyaltyRedemptionRequest(BaseModel):
    payment_id: int
    points: int = Field(gt=0)


class ReferralApplyRequest(BaseModel):
    referral_code: str = Field(min_length=4, max_length=20)
