
import re
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.models.guest import GuestIdType


class GuestCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    age: int | None = Field(default=None, ge=0, le=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    id_type: GuestIdType | None = None
    id_number_masked: str | None = Field(default=None, min_length=2, max_length=50)
    special_requests: str | None = Field(default=None, max_length=2000)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        value = value.strip()

        if len(value) < 2:
            raise ValueError("Guest name must contain at least 2 characters.")

        if not re.fullmatch(r"[\w\s.'-]+", value, flags=re.UNICODE):
            raise ValueError("Guest name contains unsupported characters.")

        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        if value and not re.fullmatch(r"\+?[0-9][0-9\s()-]{5,28}", value):
            raise ValueError("Enter a valid phone number.")

        return value or None

    @field_validator("id_number_masked")
    @classmethod
    def validate_masked_id(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        if not value:
            return None

        # Only accept a masked value, such as ****1234.
        if not re.fullmatch(r"[*Xx•-]+[0-9]{2,6}", value):
            raise ValueError(
                "Provide a masked ID reference, such as ****1234. "
                "Do not submit a full government ID number."
            )

        return value

    @model_validator(mode="after")
    def validate_identification(self):
        if self.id_number_masked and not self.id_type:
            raise ValueError(
                "Select an identification type when providing an ID reference."
            )

        if self.id_type and not self.id_number_masked:
            raise ValueError(
                "Provide a masked ID reference when specifying an ID type."
            )

        return self


class GuestUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    age: int | None = Field(default=None, ge=0, le=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    id_type: GuestIdType | None = None
    id_number_masked: str | None = Field(default=None, min_length=2, max_length=50)
    special_requests: str | None = Field(default=None, max_length=2000)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        if len(value) < 2 or not re.fullmatch(
            r"[\w\s.'-]+", value, flags=re.UNICODE
        ):
            raise ValueError("Enter a valid guest name.")

        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        if value and not re.fullmatch(r"\+?[0-9][0-9\s()-]{5,28}", value):
            raise ValueError("Enter a valid phone number.")

        return value or None

    @field_validator("id_number_masked")
    @classmethod
    def validate_masked_id(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        if not value:
            return None

        if not re.fullmatch(r"[*Xx•-]+[0-9]{2,6}", value):
            raise ValueError(
                "Provide a masked ID reference, such as ****1234."
            )

        return value

    @model_validator(mode="after")
    def validate_identification(self):
        if self.id_number_masked and not self.id_type:
            raise ValueError(
                "Select an identification type when providing an ID reference."
            )

        if self.id_type and not self.id_number_masked:
            raise ValueError(
                "Provide a masked ID reference when specifying an ID type."
            )

        return self


class GuestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reservation_id: int
    full_name: str
    age: int | None
    email: EmailStr | None
    phone: str | None
    id_type: GuestIdType | None
    id_number_masked: str | None
    special_requests: str | None
    created_at: datetime
    updated_at: datetime
