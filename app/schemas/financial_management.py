from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

from app.models.financial_management import PayoutStatus, ReconciliationStatus


class FinancialRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    payment_id: int
    hotel_id: int
    currency: str
    gross_amount: Decimal
    commission_rate: Decimal
    commission_amount: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    hotel_earnings: Decimal
    created_at: datetime


class SettlementCreate(BaseModel):
    hotel_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="inr", min_length=3, max_length=3)
    notes: str | None = None


class SettlementStatusUpdate(BaseModel):
    status: PayoutStatus
    provider_payout_reference: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class SettlementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    hotel_id: int
    amount: Decimal
    currency: str
    status: PayoutStatus
    provider_payout_reference: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ReconciliationCreate(BaseModel):
    provider_transaction_id: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    status: str = Field(min_length=1, max_length=50)


class ReconciliationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    provider_transaction_id: str
    payment_id: int | None
    provider_amount: Decimal
    local_amount: Decimal | None
    provider_status: str
    local_status: str | None
    status: ReconciliationStatus
    notes: str | None
    created_at: datetime
