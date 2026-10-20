import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SecurityAlertStatus(str, enum.Enum):
    OPEN = "OPEN"
    REVIEWED = "REVIEWED"
    RESOLVED = "RESOLVED"


class SecurityAlert(Base):
    __tablename__ = "security_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    alert_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="MEDIUM")
    status: Mapped[SecurityAlertStatus] = mapped_column(
        Enum(SecurityAlertStatus, name="security_alert_status"),
        nullable=False, default=SecurityAlertStatus.OPEN, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True, index=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
