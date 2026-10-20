
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    func,
)

from app.db.session import Base


class TravelConversation(Base):
    __tablename__ = "travel_conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    destination = Column(String(100), nullable=False)
    budget = Column(Numeric(12, 2), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    preferences = Column(JSON, nullable=False, default=list)
    travel_plan = Column(JSON, nullable=False)
    ai_provider = Column(String(30), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
