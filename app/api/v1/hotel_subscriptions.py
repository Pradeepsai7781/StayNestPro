
import calendar
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import Hotel, User, UserRole
from app.models.hotel_subscription import (
    BillingPeriod,
    HotelSubscription,
    SubscriptionPlan,
    SubscriptionStatus,
)
from app.schemas.hotel_subscription import (
    HotelSubscriptionCreate,
    HotelSubscriptionUpdate,
    HotelSubscriptionResponse,
    SubscriptionPlanBenefitsResponse,
)
from app.services.subscription_plan_service import (
    SUBSCRIPTION_PLAN_BENEFITS,
    get_subscription_plan_benefits,
)
from app.services.stripe_subscription_service import (
    change_stripe_subscription_plan,
    cancel_stripe_subscription,
)

router = APIRouter(
    prefix="/hotel-subscriptions",
    tags=["Hotel Subscription Plans"],
)


def require_admin_or_owner(user: User) -> None:
    if user.role not in (UserRole.ADMIN, UserRole.HOTEL_OWNER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only hotel owners or administrators can manage subscriptions.",
        )


def get_authorized_hotel(
    db: Session,
    hotel_id: int,
    user: User,
) -> Hotel:
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()

    if hotel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hotel not found.",
        )

    if user.role != UserRole.ADMIN and hotel.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this hotel.",
        )

    return hotel


def calculate_expiry(
    started_at: datetime,
    billing_period: BillingPeriod,
) -> datetime:
    if billing_period == BillingPeriod.YEARLY:
        target_year = started_at.year + 1
        target_month = started_at.month
    else:
        target_year = started_at.year
        target_month = started_at.month + 1

        if target_month > 12:
            target_month = 1
            target_year += 1

    last_day = calendar.monthrange(target_year, target_month)[1]

    return started_at.replace(
        year=target_year,
        month=target_month,
        day=min(started_at.day, last_day),
    )


def update_expiry_status(subscription: HotelSubscription) -> None:
    if (
        subscription.status != SubscriptionStatus.ACTIVE
        or subscription.expires_at is None
    ):
        return

    expires_at = subscription.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at <= datetime.now(timezone.utc):
        subscription.status = SubscriptionStatus.EXPIRED


@router.get(
    "/plans",
    response_model=list[SubscriptionPlanBenefitsResponse],
)
def get_subscription_plans():
    return [
        SubscriptionPlanBenefitsResponse(
            plan=plan,
            **get_subscription_plan_benefits(plan),
        )
        for plan in SubscriptionPlan
    ]


@router.get(
    "/plans/{plan}",
    response_model=SubscriptionPlanBenefitsResponse,
)
def get_subscription_plan(plan: SubscriptionPlan):
    return SubscriptionPlanBenefitsResponse(
        plan=plan,
        **get_subscription_plan_benefits(plan),
    )


@router.post(
    "",
    response_model=HotelSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_hotel_subscription(
    subscription_data: HotelSubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin_or_owner(current_user)
    get_authorized_hotel(db, subscription_data.hotel_id, current_user)

    existing_subscription = (
        db.query(HotelSubscription)
        .filter(HotelSubscription.hotel_id == subscription_data.hotel_id)
        .first()
    )

    if existing_subscription is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A subscription already exists for this hotel.",
        )

    started_at = datetime.now(timezone.utc)

    subscription = HotelSubscription(
        hotel_id=subscription_data.hotel_id,
        plan=subscription_data.plan,
        billing_period=subscription_data.billing_period,
        status=SubscriptionStatus.ACTIVE,
        started_at=started_at,
        expires_at=calculate_expiry(
            started_at,
            subscription_data.billing_period,
        ),
    )

    try:
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
    except Exception:
        db.rollback()
        raise

    return subscription


@router.get(
    "/hotels/{hotel_id}",
    response_model=HotelSubscriptionResponse,
)
def get_hotel_subscription(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_authorized_hotel(db, hotel_id, current_user)

    subscription = (
        db.query(HotelSubscription)
        .filter(HotelSubscription.hotel_id == hotel_id)
        .first()
    )

    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found for this hotel.",
        )

    update_expiry_status(subscription)

    try:
        db.commit()
        db.refresh(subscription)
    except Exception:
        db.rollback()
        raise

    return subscription


@router.patch(
    "/hotels/{hotel_id}",
    response_model=HotelSubscriptionResponse,
)
def update_hotel_subscription(
    hotel_id: int,
    subscription_data: HotelSubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upgrade or downgrade the plan and update Stripe when configured."""
    require_admin_or_owner(current_user)
    get_authorized_hotel(db, hotel_id, current_user)

    subscription = (
        db.query(HotelSubscription)
        .filter(HotelSubscription.hotel_id == hotel_id)
        .first()
    )

    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found for this hotel.",
        )

    # Do not update a paid Stripe subscription locally unless its Stripe
    # plan change has also succeeded.
    if subscription.stripe_subscription_id:
        from app.services.stripe_price_service import get_stripe_price_id

        price_id = get_stripe_price_id(
            subscription_data.plan,
            subscription_data.billing_period,
        )

        change_stripe_subscription_plan(
            subscription.stripe_subscription_id,
            price_id,
        )

    subscription.plan = subscription_data.plan
    subscription.billing_period = subscription_data.billing_period
    subscription.started_at = datetime.now(timezone.utc)
    subscription.expires_at = calculate_expiry(
        subscription.started_at,
        subscription.billing_period,
    )
    subscription.status = SubscriptionStatus.ACTIVE

    try:
        db.commit()
        db.refresh(subscription)
    except Exception:
        db.rollback()
        raise

    return subscription


@router.patch(
    "/hotels/{hotel_id}/cancel",
    response_model=HotelSubscriptionResponse,
)
def cancel_hotel_subscription(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin_or_owner(current_user)
    get_authorized_hotel(db, hotel_id, current_user)

    subscription = (
        db.query(HotelSubscription)
        .filter(HotelSubscription.hotel_id == hotel_id)
        .first()
    )

    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found for this hotel.",
        )

    if subscription.stripe_subscription_id:
        cancel_stripe_subscription(subscription.stripe_subscription_id)

    subscription.status = SubscriptionStatus.CANCELLED

    try:
        db.commit()
        db.refresh(subscription)
    except Exception:
        db.rollback()
        raise

    return subscription


@router.get(
    "/hotels/{hotel_id}/benefits",
    response_model=SubscriptionPlanBenefitsResponse,
)
def get_hotel_subscription_benefits(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_authorized_hotel(db, hotel_id, current_user)

    subscription = (
        db.query(HotelSubscription)
        .filter(HotelSubscription.hotel_id == hotel_id)
        .first()
    )

    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found for this hotel.",
        )

    update_expiry_status(subscription)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return SubscriptionPlanBenefitsResponse(
        plan=subscription.plan,
        **SUBSCRIPTION_PLAN_BENEFITS[subscription.plan],
    )
