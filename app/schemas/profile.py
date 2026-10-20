from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class CustomerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    phone_number: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    travel_preferences: dict[str, Any] | None = None
    profile_picture: str | None = None


class CustomerProfileUpdate(BaseModel):
    full_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )
    phone_number: str | None = Field(
        default=None,
        max_length=20,
    )
    address: str | None = Field(
        default=None,
        max_length=255,
    )
    city: str | None = Field(
        default=None,
        max_length=100,
    )
    state: str | None = Field(
        default=None,
        max_length=100,
    )
    postal_code: str | None = Field(
        default=None,
        max_length=20,
    )
    country: str | None = Field(
        default=None,
        max_length=100,
    )
    travel_preferences: dict[str, Any] | None = None

    @field_validator("travel_preferences")
    @classmethod
    def validate_travel_preferences(
        cls,
        value: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if value is not None and len(value) > 50:
            raise ValueError("Travel preferences cannot contain more than 50 entries")
        return value
