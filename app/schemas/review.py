
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HotelReviewCreate(BaseModel):
    reservation_id: int = Field(gt=0)
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=5000)


class HotelReviewUpdate(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=5000)


class HotelReviewResponse(BaseModel):
    id: int
    reservation_id: int
    hotel_id: int
    user_id: int
    rating: int = Field(ge=1, le=5)
    comment: str | None
    is_reported: bool
    is_hidden: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HotelReviewReport(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
