
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.services.recommendation_service import (
    get_recommendations,
    get_similar_hotels,
)
from app.services.ai_recommendation_service import (
    get_ai_recommendations,
)

router = APIRouter(
    prefix="/recommendations",
    tags=["Hotel Recommendations"],
)

require_customer = require_roles(UserRole.CUSTOMER)


@router.get("")
def personalized_recommendations(
    budget: float | None = Query(default=None, gt=0),
    city: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    # Always get valid recommendations from the existing engine first.
    recommendations = get_recommendations(
        db=db,
        user_id=current_user.id,
        budget=budget,
        city=city,
        limit=limit,
    )

    recommendation_method = "rule_based_fallback"

    # Gemini is optional; failures return None.
    ai_recommendations = get_ai_recommendations(
        hotels=recommendations,
        budget=budget,
        city=city,
    )

    if ai_recommendations is not None:
        recommendations = ai_recommendations
        recommendation_method = "gemini"

    return {
        "user_id": current_user.id,
        "recommendation_method": recommendation_method,
        "count": len(recommendations),
        "recommendations": recommendations,
    }


@router.get("/similar/{hotel_id}")
def similar_hotels(
    hotel_id: int,
    limit: int = Query(default=5, ge=1, le=20),
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    recommendations = get_similar_hotels(
        db=db,
        hotel_id=hotel_id,
        limit=limit,
    )

    return {
        "hotel_id": hotel_id,
        "count": len(recommendations),
        "recommendations": recommendations,
    }
