
from datetime import time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.hotel import PropertyType
from app.models.hotel_image import HotelImageCategory
from app.models.room_type import RoomTypeCategory
from app.schemas.review import HotelReviewResponse


class HotelDetailRoomType(BaseModel):
    id: int
    name: RoomTypeCategory
    description: str | None
    price_per_night: Decimal
    capacity: int
    amenities: list[str]
    images: list[str]

    model_config = ConfigDict(from_attributes=True)


class HotelDetailAmenity(BaseModel):
    id: int
    name: str
    description: str | None

    model_config = ConfigDict(from_attributes=True)


class HotelDetailImage(BaseModel):
    id: int
    image_url: str
    caption: str | None
    category: HotelImageCategory
    display_order: int
    is_primary: bool

    model_config = ConfigDict(from_attributes=True)


class HotelDetailsResponse(BaseModel):
    id: int
    name: str
    description: str | None
    property_type: PropertyType
    rating: float | None

    address: str
    city: str
    state: str
    postal_code: str
    country: str
    latitude: float | None
    longitude: float | None

    policies: dict | None
    check_in_time: time | None
    check_out_time: time | None
    check_in_rules: str | None

    room_types: list[HotelDetailRoomType]
    amenities: list[HotelDetailAmenity]
    gallery: list[HotelDetailImage]
    reviews: list[HotelReviewResponse] = []

    model_config = ConfigDict(from_attributes=True)
