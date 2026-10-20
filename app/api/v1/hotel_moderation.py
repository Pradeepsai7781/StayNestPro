
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.permissions import require_roles
from app.db.session import get_db
from app.models import HotelStatus, User, UserRole
from app.schemas.hotel_moderation import (
    HotelModerationDecisionRequest,
    HotelModerationResponse,
    HotelVerificationDocumentResponse,
    ReportedReviewResponse,
)
from app.services.hotel_moderation_service import (
    get_hotel_verification_documents,
    get_reported_properties,
    get_reported_reviews,
    moderate_hotel,
    moderate_reported_property,
    moderate_reported_review,
)

router = APIRouter(
    prefix="/admin/hotel-moderation",
    tags=["Hotel Verification and Moderation"],
)

require_admin = require_roles(UserRole.ADMIN)


@router.get(
    "/documents",
    response_model=list[HotelVerificationDocumentResponse],
)
def list_verification_documents(
    hotel_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    __: User = Depends(require_admin),
):
    return get_hotel_verification_documents(
        db=db,
        hotel_id=hotel_id,
    )


@router.patch(
    "/hotels/{hotel_id}/decision",
    response_model=HotelModerationResponse,
)
def decide_hotel_application(
    hotel_id: int,
    decision: HotelStatus = Query(...),
    payload: HotelModerationDecisionRequest = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_admin),
):
    return moderate_hotel(
        db=db,
        hotel_id=hotel_id,
        decision=decision,
        reason=payload.reason,
        admin_id=current_user.id,
    )


@router.get(
    "/reported-reviews",
    response_model=list[ReportedReviewResponse],
)
def list_reported_reviews(
    hotel_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    __: User = Depends(require_admin),
):
    return get_reported_reviews(
        db=db,
        hotel_id=hotel_id,
    )


@router.patch("/reported-reviews/{review_id}/moderation")
def moderate_review(
    review_id: int,
    hide: bool = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    __: User = Depends(require_admin),
):
    return moderate_reported_review(
        db=db,
        review_id=review_id,
        hide=hide,
    )


@router.get("/reported-properties")
def list_reported_properties(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    __: User = Depends(require_admin),
):
    return get_reported_properties(db=db)


@router.patch("/reported-properties/{hotel_id}/moderation")
def moderate_property(
    hotel_id: int,
    reason: str = Query(..., min_length=1),
    suspend: bool = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_admin),
):
    return moderate_reported_property(
        db=db,
        hotel_id=hotel_id,
        reason=reason,
        admin_id=current_user.id,
        suspend=suspend,
    )
