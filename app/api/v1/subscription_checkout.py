
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import Hotel, User, UserRole
from app.models.hotel_subscription import (
    BillingPeriod,
    HotelSubscription,
    SubscriptionPlan,
)
from app.services.stripe_subscription_service import (
    create_stripe_customer,
    create_subscription_checkout_session,
)
from app.services.stripe_price_service import get_stripe_price_id


router = APIRouter(
    prefix="/subscription-checkout",
    tags=["Subscription Payments"],
)


class SubscriptionCheckoutRequest(BaseModel):
    hotel_id: int
    plan: SubscriptionPlan
    billing_period: BillingPeriod
    success_url: HttpUrl
    cancel_url: HttpUrl


@router.post("/create")
def create_subscription_checkout(
    checkout_data: SubscriptionCheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (UserRole.ADMIN, UserRole.HOTEL_OWNER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only hotel owners or administrators can start subscription checkout.",
        )

    hotel = (
        db.query(Hotel)
        .filter(Hotel.id == checkout_data.hotel_id)
        .first()
    )

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
            detail="You are not authorized to manage this hotel's subscription.",
        )

    subscription = (
        db.query(HotelSubscription)
        .filter(HotelSubscription.hotel_id == hotel.id)
        .first()
    )

    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Create the hotel's subscription record before starting checkout.",
        )

    price_id = get_stripe_price_id(
        checkout_data.plan,
        checkout_data.billing_period,
    )

    try:
        customer_id = subscription.stripe_customer_id

        if not customer_id:
            customer = create_stripe_customer(
                email=current_user.email,
                hotel_id=hotel.id,
            )
            customer_id = customer.id
            subscription.stripe_customer_id = customer_id
            db.commit()

        checkout_session = create_subscription_checkout_session(
            customer_id=customer_id,
            price_id=price_id,
            success_url=str(checkout_data.success_url),
            cancel_url=str(checkout_data.cancel_url),
            hotel_id=hotel.id,
        )

        return {
            "checkout_url": checkout_session.url,
            "checkout_session_id": checkout_session.id,
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to start Stripe subscription checkout.",
        )