
from datetime import time

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
)


class HotelCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    description: str | None = None
    email: EmailStr
    phone_number: str = Field(min_length=7, max_length=20)
    address: str = Field(min_length=3, max_length=255)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    postal_code: str = Field(min_length=3, max_length=20)
    country: str = Field(min_length=2, max_length=100)

    # Optional hotel coordinates
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class HotelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = None
    email: EmailStr | None = None
    phone_number: str | None = Field(default=None, min_length=7, max_length=20)
    address: str | None = Field(default=None, min_length=3, max_length=255)
    city: str | None = Field(default=None, min_length=2, max_length=100)
    state: str | None = Field(default=None, min_length=2, max_length=100)
    postal_code: str | None = Field(default=None, min_length=3, max_length=20)
    country: str | None = Field(default=None, min_length=2, max_length=100)

    policies: dict[str, str | bool | int | float | None] | None = None
    check_in_time: time | None = None
    check_out_time: time | None = None
    check_in_rules: str | None = None

    # Optional coordinates for nearby hotel searches
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class HotelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    name: str
    description: str | None
    email: EmailStr
    phone_number: str
    address: str
    city: str
    state: str
    postal_code: str
    country: str
    status: str

    policies: dict | None = None
    check_in_time: time | None = None
    check_out_time: time | None = None
    check_in_rules: str | None = None

    latitude: float | None = None
    longitude: float | None = None


class HotelImageCreate(BaseModel):
    image_url: HttpUrl
    caption: str | None = Field(default=None, max_length=255)
    category: str = "GENERAL"
    display_order: int = Field(default=0, ge=0)
    is_primary: bool = False


class HotelImageUpdate(BaseModel):
    image_url: HttpUrl | None = None
    caption: str | None = Field(default=None, max_length=255)
    category: str | None = None
    display_order: int | None = Field(default=None, ge=0)
    is_primary: bool | None = None


class HotelImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    image_url: str
    caption: str | None
    category: str
    display_order: int
    is_primary: bool
