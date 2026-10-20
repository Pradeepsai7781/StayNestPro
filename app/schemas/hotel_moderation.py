
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HotelModerationDecisionRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class HotelModerationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hotel_id: int
    hotel_name: str
    status: str
    decision_reason: str | None
    decision_by: int | None
    decision_at: datetime | None


class HotelVerificationDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    document_type: str
    original_filename: str
    content_type: str
    uploaded_at: datetime


class ReportedReviewResponse(BaseModel):
    id: int
    hotel_id: int
    rating: int
    comment: str | None
    report_reason: str | None
    is_reported: bool
    is_hidden: bool
    created_at: datetime
