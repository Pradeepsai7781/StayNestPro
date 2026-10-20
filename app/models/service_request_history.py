
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.additional_service import ServiceRequestStatus


class ServiceRequestHistory(Base):
    __tablename__ = "service_request_history"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    service_request_id: Mapped[int] = mapped_column(
        ForeignKey("service_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[ServiceRequestStatus] = mapped_column(
        Enum(
            ServiceRequestStatus,
            name="service_request_history_status",
        ),
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
