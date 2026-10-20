
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.room import RoomStatus


class RoomCreate(BaseModel):
    room_type_id: int = Field(gt=0)
    room_number: str = Field(min_length=1, max_length=30)
    capacity: int = Field(ge=1, le=100)
    status: RoomStatus = RoomStatus.AVAILABLE


class RoomUpdate(BaseModel):
    room_type_id: int | None = Field(default=None, gt=0)
    room_number: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
    )
    capacity: int | None = Field(default=None, ge=1, le=100)
    status: RoomStatus | None = None


class RoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    room_type_id: int
    room_number: str
    capacity: int
    status: RoomStatus
    created_at: datetime
    updated_at: datetime
