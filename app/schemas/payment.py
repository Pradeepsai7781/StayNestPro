
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.payment import PaymentStatus


class PaymentCheckoutRequest(BaseModel):
    reservation_id: int = Field(gt=0)
    idempotency_key: str = Field(min_length=8, max_length=255)


class PaymentSimulationRequest(BaseModel):
    status: PaymentStatus


class MockPaymentEventRequest(BaseModel):
    event_id: str = Field(min_length=8, max_length=255)
    payment_id: int = Field(gt=0)
    status: PaymentStatus


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reservation_id: int
    customer_id: int
    amount: Decimal
    currency: str
    status: PaymentStatus
    stripe_checkout_session_id: str | None
    stripe_payment_intent_id: str | None
    created_at: datetime
    updated_at: datetime
