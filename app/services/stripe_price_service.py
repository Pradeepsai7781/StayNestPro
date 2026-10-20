
import os

from fastapi import HTTPException, status

from app.models.hotel_subscription import BillingPeriod, SubscriptionPlan


STRIPE_PRICE_ENV_KEYS = {
    (SubscriptionPlan.FREE, BillingPeriod.MONTHLY): "STRIPE_PRICE_FREE_MONTHLY",
    (SubscriptionPlan.FREE, BillingPeriod.YEARLY): "STRIPE_PRICE_FREE_YEARLY",
    (SubscriptionPlan.BASIC, BillingPeriod.MONTHLY): "STRIPE_PRICE_BASIC_MONTHLY",
    (SubscriptionPlan.BASIC, BillingPeriod.YEARLY): "STRIPE_PRICE_BASIC_YEARLY",
    (SubscriptionPlan.PREMIUM, BillingPeriod.MONTHLY): "STRIPE_PRICE_PREMIUM_MONTHLY",
    (SubscriptionPlan.PREMIUM, BillingPeriod.YEARLY): "STRIPE_PRICE_PREMIUM_YEARLY",
    (SubscriptionPlan.ENTERPRISE, BillingPeriod.MONTHLY): "STRIPE_PRICE_ENTERPRISE_MONTHLY",
    (SubscriptionPlan.ENTERPRISE, BillingPeriod.YEARLY): "STRIPE_PRICE_ENTERPRISE_YEARLY",
}


def get_stripe_price_id(
    plan: SubscriptionPlan,
    billing_period: BillingPeriod,
) -> str:
    """Return the Stripe recurring Price ID configured for a plan."""
    env_key = STRIPE_PRICE_ENV_KEYS.get((plan, billing_period))

    if env_key is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid subscription plan or billing period.",
        )

    price_id = os.getenv(env_key, "").strip()

    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Stripe Price ID is not configured for {plan.value} {billing_period.value} billing.",
        )

    return price_id
