
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.models.dynamic_pricing import (
    PricingAdjustmentType,
    PricingRuleType,
)


class DynamicPricingCreate(BaseModel):
    room_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=150)
    rule_type: PricingRuleType
    adjustment_type: PricingAdjustmentType
    adjustment_value: Decimal = Field(ge=0)
    start_date: date
    end_date: date
    priority: int = Field(default=1, ge=1)
    description: Optional[str] = None

    @model_validator(mode="after")
    def validate_pricing_rule(self):
        if self.end_date < self.start_date:
            raise ValueError(
                "End date must be on or after start date."
            )

        if (
            self.rule_type == PricingRuleType.PROMOTIONAL
            and self.adjustment_type == PricingAdjustmentType.PERCENTAGE
            and self.adjustment_value > Decimal("100")
        ):
            raise ValueError(
                "Promotional percentage cannot exceed 100."
            )

        return self


class DynamicPricingUpdate(BaseModel):
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=150,
    )
    rule_type: Optional[PricingRuleType] = None
    adjustment_type: Optional[PricingAdjustmentType] = None
    adjustment_value: Optional[Decimal] = Field(
        default=None,
        ge=0,
    )
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    priority: Optional[int] = Field(default=None, ge=1)
    description: Optional[str] = None


class DynamicPricingResponse(BaseModel):
    id: int
    room_id: int
    name: str
    rule_type: PricingRuleType
    adjustment_type: PricingAdjustmentType
    adjustment_value: Decimal
    start_date: date
    end_date: date
    priority: int
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoomPriceResponse(BaseModel):
    room_id: int
    check_in: date
    check_out: date
    number_of_nights: int
    nightly_prices: list[Decimal]
    total_price: Decimal
    applied_rules: list[str]
