import enum
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AuditEventType(str, enum.Enum):
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    LOGIN_FAILED = "LOGIN_FAILED"
    BOOKING_CREATED = "BOOKING_CREATED"
    BOOKING_UPDATED = "BOOKING_UPDATED"
    BOOKING_CANCELLED = "BOOKING_CANCELLED"
    PAYMENT_CREATED = "PAYMENT_CREATED"
    PAYMENT_SUCCEEDED = "PAYMENT_SUCCEEDED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    ADMIN_ACTION = "ADMIN_ACTION"
    STAFF_ACTIVITY = "STAFF_ACTIVITY"
    SECURITY_EVENT = "SECURITY_EVENT"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    __table_args__ = (
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_event_type", "event_type"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    event_type: Mapped[AuditEventType] = mapped_column(
        Enum(AuditEventType, name="audit_event_type"),
        nullable=False,
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    entity_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    entity_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    details: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )