
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.audit_log import AuditEventType


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: int | None
    event_type: AuditEventType
    action: str
    description: str | None
    entity_type: str | None
    entity_id: str | None
    ip_address: str | None
    details: dict | None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
