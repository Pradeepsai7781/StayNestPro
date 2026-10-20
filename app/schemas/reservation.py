
from datetime import date, datetime
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.models.reservation import ReservationStatus


class ReservationCreate(BaseModel):
    room_id: int = Field(gt=0)
    check_in: date
    check_out: date
    guest_count: int = Field(default=1, ge=1, le=100)
    coupon_code: str | None = Field(
        default=None,
        min_length=3,
        max_length=50,
    )

    @model_validator(mode="after")
    def validate_booking_dates(self):
        if self.check_in < date.today():
            raise ValueError("Check-in date cannot be in the past.")

        if self.check_out <= self.check_in:
            raise ValueError("Check-out must be after check-in.")

        if self.coupon_code is not None:
            self.coupon_code = self.coupon_code.strip().upper()

        return self


class ReservationModify(BaseModel):
    room_id: int | None = Field(default=None, gt=0)
    check_in: date | None = None
    check_out: date | None = None
    guest_count: int | None = Field(default=None, ge=1, le=100)

    @model_validator(mode="after")
    def validate_booking_dates(self):
        if self.check_in is not None and self.check_in < date.today():
            raise ValueError("Check-in date cannot be in the past.")

        if (
            self.check_in is not None
            and self.check_out is not None
            and self.check_out <= self.check_in
        ):
            raise ValueError("Check-out must be after check-in.")

        if not self.model_fields_set:
            raise ValueError("Provide at least one field to modify.")

        return self


class ReservationStatusUpdate(BaseModel):
    status: ReservationStatus


class ReservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    customer_id: int
    check_in: date
    check_out: date
    guest_count: int
    booking_reference: str
    total_price: Decimal
    status: ReservationStatus
    created_at: datetime
    updated_at: datetime


class ReservationCancelResponse(BaseModel):
    message: str
    reservation_id: int
    status: ReservationStatus
