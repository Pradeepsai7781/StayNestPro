
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import UserRole


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    role: UserRole
    is_active: bool
    is_email_verified: bool


class UserRoleUpdate(BaseModel):
    role: UserRole


class UserStatusUpdate(BaseModel):
    is_active: bool = Field(...)


class HotelDecisionRequest(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
