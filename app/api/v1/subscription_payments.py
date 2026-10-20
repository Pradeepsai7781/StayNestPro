
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import Hotel, HotelSubscription, User, UserRole
from app.models.subscription_payment import (
    SubscriptionPayment,
    SubscriptionPaymentStatus,
)


router = APIRouter(
    prefix="/subscription-payments",
    tags=["Subscription Payments"],
)


class SubscriptionPaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_subscription_id: int
    stripe_payment_intent_id: str | None
    stripe_invoice_id: str | None
    amount: float
    currency: str
    status: SubscriptionPaymentStatus


@router.get(
    "/hotels/{hotel_id}/history",
    response_model=list[SubscriptionPaymentResponse],
)
def get_subscription_payment_history(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return payment history for a hotel owned by the current user or an admin."""
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()

    if hotel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hotel not found.",
        )

    if (
        current_user.role != UserRole.ADMIN
        and hotel.owner_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this hotel's payment history.",
        )

    return (
        db.query(SubscriptionPayment)
        .join(
            HotelSubscription,
            SubscriptionPayment.hotel_subscription_id == HotelSubscription.id,
        )
        .filter(HotelSubscription.hotel_id == hotel_id)
        .order_by(SubscriptionPayment.created_at.desc())
        .all()
    )
