
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class RoomAssignmentRequest(BaseModel):
    room_id: int = Field(gt=0)


class ReservationStayResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reservation_id: int
    actual_check_in: datetime | None
    actual_check_out: datetime | None
    early_check_in_charge: Decimal
    late_check_out_charge: Decimal
    created_at: datetime
    updated_at: datetime


class CheckInRequest(BaseModel):
    early_check_in_charge: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        max_digits=10,
        decimal_places=2,
    )


class CheckOutRequest(BaseModel):
    late_check_out_charge: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
