
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.coupon import CouponType


class CouponCreate(BaseModel):
    code: str = Field(min_length=3, max_length=50)
    description: str | None = Field(default=None, max_length=255)
    coupon_type: CouponType
    discount_value: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    min_booking_amount: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
    valid_from: datetime
    expires_at: datetime
    usage_limit: int | None = Field(default=None, gt=0)
    is_active: bool = True
    is_seasonal: bool = False
    is_early_booking: bool = False

    @model_validator(mode="after")
    def validate_coupon(self):
        if self.expires_at <= self.valid_from:
            raise ValueError("Expiry must be later than the start date.")

        if self.coupon_type == CouponType.PERCENTAGE:
            if self.discount_value > 100:
                raise ValueError("Percentage discount cannot exceed 100.")

        return self


class CouponResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    description: str | None
    coupon_type: CouponType
    discount_value: Decimal
    min_booking_amount: Decimal
    valid_from: datetime
    expires_at: datetime
    usage_limit: int | None
    used_count: int
    is_active: bool
    is_seasonal: bool
    is_early_booking: bool
    created_at: datetime


class CouponApplyRequest(BaseModel):
    code: str = Field(min_length=3, max_length=50)
    booking_amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    check_in: datetime


class CouponApplyResponse(BaseModel):
    code: str
    coupon_type: CouponType
    discount_value: Decimal
    discount_amount: Decimal
    final_amount: Decimal
