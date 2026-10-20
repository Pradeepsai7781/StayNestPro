
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.models.room_type import RoomTypeCategory


class RoomTypeCreate(BaseModel):
    name: RoomTypeCategory
    description: str | None = Field(default=None, max_length=1000)
    price_per_night: Decimal = Field(
        gt=0,
        max_digits=10,
        decimal_places=2,
    )
    capacity: int = Field(ge=1, le=100)
    amenities: list[str] = Field(default_factory=list, max_length=50)
    images: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("amenities")
    @classmethod
    def validate_amenities(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]

        if any(not item for item in cleaned):
            raise ValueError("Amenities cannot contain empty values")

        if any(len(item) > 100 for item in cleaned):
            raise ValueError("Each amenity must be at most 100 characters")

        return cleaned

    @field_validator("images")
    @classmethod
    def validate_images(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]

        if any(not item for item in cleaned):
            raise ValueError("Image URLs cannot be empty")

        if any(
            not item.startswith(("https://", "http://"))
            for item in cleaned
        ):
            raise ValueError("Images must use HTTP or HTTPS URLs")

        return cleaned


class RoomTypeUpdate(BaseModel):
    name: RoomTypeCategory | None = None
    description: str | None = Field(default=None, max_length=1000)
    price_per_night: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=10,
        decimal_places=2,
    )
    capacity: int | None = Field(default=None, ge=1, le=100)
    amenities: list[str] | None = Field(default=None, max_length=50)
    images: list[str] | None = Field(default=None, max_length=20)

    @field_validator("amenities")
    @classmethod
    def validate_amenities(cls, value: list[str] | None):
        if value is None:
            return value

        cleaned = [item.strip() for item in value]

        if any(not item for item in cleaned):
            raise ValueError("Amenities cannot contain empty values")

        if any(len(item) > 100 for item in cleaned):
            raise ValueError("Each amenity must be at most 100 characters")

        return cleaned

    @field_validator("images")
    @classmethod
    def validate_images(cls, value: list[str] | None):
        if value is None:
            return value

        cleaned = [item.strip() for item in value]

        if any(not item for item in cleaned):
            raise ValueError("Image URLs cannot be empty")

        if any(
            not item.startswith(("https://", "http://"))
            for item in cleaned
        ):
            raise ValueError("Images must use HTTP or HTTPS URLs")

        return cleaned


class RoomTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    name: RoomTypeCategory
    description: str | None
    price_per_night: Decimal
    capacity: int
    amenities: list[str]
    images: list[str]
