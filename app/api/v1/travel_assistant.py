
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.db.session import get_db
from app.models import (
    Hotel,
    HotelStatus,
    RoomType,
    User,
    UserRole,
    TravelConversation,
)
from app.services.travel_assistant_service import create_travel_plan

router = APIRouter(
    prefix="/travel-assistant",
    tags=["AI Travel Assistant"],
)

require_customer = require_roles(UserRole.CUSTOMER)


class TravelPlanRequest(BaseModel):
    budget: float = Field(gt=0)
    destination: str = Field(min_length=2, max_length=100)
    start_date: date
    end_date: date
    preferences: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("End date must be on or after start date.")
        if self.start_date < date.today():
            raise ValueError("Start date cannot be in the past.")

        for preference in self.preferences:
            if not preference.strip() or len(preference) > 100:
                raise ValueError(
                    "Each preference must contain 1–100 characters."
                )

        return self


@router.post("/plan")
def plan_trip(
    request: TravelPlanRequest,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    destination = request.destination.strip()

    hotels = (
        db.query(Hotel)
        .join(RoomType, RoomType.hotel_id == Hotel.id)
        .filter(
            Hotel.status == HotelStatus.APPROVED,
            Hotel.city.ilike(f"%{destination}%"),
            RoomType.price_per_night <= request.budget,
        )
        .distinct()
        .all()
    )

    hotel_data = [
        {
            "hotel_id": hotel.id,
            "name": hotel.name,
            "city": hotel.city,
            "country": hotel.country,
            "property_type": hotel.property_type.value,
            "rating": hotel.rating,
        }
        for hotel in hotels
    ]

    plan = create_travel_plan(
        budget=request.budget,
        destination=destination,
        start_date=request.start_date.isoformat(),
        end_date=request.end_date.isoformat(),
        preferences=request.preferences,
        hotels=hotel_data,
    )

    method = "gemini"

    if plan is None:
        method = "rule_based_fallback"
        plan = {
            "destination": destination,
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
            "suggestions": [
                f"Explore attractions in {destination}.",
                "Choose activities that match your travel preferences.",
            ],
            "hotel_suggestions": [
                {
                    "hotel_id": hotel["hotel_id"],
                    "name": hotel["name"],
                    "reason": "Approved hotel within your budget.",
                }
                for hotel in hotel_data
            ],
            "itinerary": [
                "Plan sightseeing and activities based on your dates."
            ],
        }

    conversation = TravelConversation(
        user_id=current_user.id,
        destination=destination,
        budget=request.budget,
        start_date=request.start_date,
        end_date=request.end_date,
        preferences=request.preferences,
        travel_plan=plan,
        ai_provider=method,
    )

    try:
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    except Exception:
        db.rollback()
        raise

    return {
        "conversation_id": conversation.id,
        "user_id": current_user.id,
        "method": method,
        "plan": plan,
    }


@router.get("/conversations")
def get_travel_conversations(
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    conversations = (
        db.query(TravelConversation)
        .filter(TravelConversation.user_id == current_user.id)
        .order_by(TravelConversation.created_at.desc())
        .all()
    )

    return {
        "user_id": current_user.id,
        "count": len(conversations),
        "conversations": [
            {
                "conversation_id": conversation.id,
                "destination": conversation.destination,
                "budget": float(conversation.budget),
                "start_date": conversation.start_date.isoformat(),
                "end_date": conversation.end_date.isoformat(),
                "preferences": conversation.preferences,
                "method": conversation.ai_provider,
                "plan": conversation.travel_plan,
                "created_at": (
                    conversation.created_at.isoformat()
                    if conversation.created_at
                    else None
                ),
            }
            for conversation in conversations
        ],
    }
