
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    conversation_type: Literal["HOTEL", "SUPPORT"]
    participant_id: int | None = None
    subject: str | None = Field(default=None, max_length=200)


class ConversationResponse(BaseModel):
    id: int
    customer_id: int
    participant_id: int
    conversation_type: str
    subject: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    content: str
    status: str
    created_at: datetime
    read_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class MessagePage(BaseModel):
    items: list[MessageResponse]
    total: int
    page: int
    page_size: int
    unread_count: int
