
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.additional_service import (
    AdditionalServiceCategory,
    ServiceRequestStatus,
)


# ---------------------------------------------------------
# ADDITIONAL SERVICE SCHEMAS
# ---------------------------------------------------------

class AdditionalServiceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    category: AdditionalServiceCategory
    description: str | None = None
    price: Decimal = Field(
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
    is_available: bool = True


class AdditionalServiceUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )
    category: AdditionalServiceCategory | None = None
    description: str | None = None
    price: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
    is_available: bool | None = None


class AdditionalServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: AdditionalServiceCategory
    description: str | None
    price: Decimal
    is_available: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------
# SERVICE REQUEST SCHEMAS
# ---------------------------------------------------------

class ServiceRequestCreate(BaseModel):
    reservation_id: int = Field(gt=0)
    service_id: int = Field(gt=0)
    quantity: int = Field(default=1, ge=1)
    special_instructions: str | None = Field(
        default=None,
        max_length=1000,
    )


class ServiceRequestUpdate(BaseModel):
    status: ServiceRequestStatus


class ServiceRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reservation_id: int
    service_id: int
    requested_by: int
    quantity: int
    unit_price: Decimal
    total_charge: Decimal
    status: ServiceRequestStatus
    special_instructions: str | None
    requested_at: datetime
    updated_at: datetime
    completed_at: datetime | None


# ---------------------------------------------------------
# SERVICE REQUEST HISTORY SCHEMA
# ---------------------------------------------------------

class ServiceRequestHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service_request_id: int
    status: ServiceRequestStatus
    notes: str | None
    changed_at: datetime
