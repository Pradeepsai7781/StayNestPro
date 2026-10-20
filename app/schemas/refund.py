
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.refund import RefundStatus


class RefundRequestCreate(BaseModel):
    payment_id: int = Field(gt=0)
    reason: str = Field(min_length=5, max_length=1000)


class RefundReviewRequest(BaseModel):
    status: RefundStatus
    review_note: str | None = Field(default=None, max_length=1000)


class RefundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    payment_id: int
    reservation_id: int
    customer_id: int
    amount: Decimal
    currency: str
    status: RefundStatus
    reason: str
    reviewed_by: int | None
    review_note: str | None
    stripe_refund_id: str | None
    created_at: datetime
    updated_at: datetime