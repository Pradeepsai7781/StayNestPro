
from app.models.hotel_subscription import SubscriptionPlan


SUBSCRIPTION_PLAN_BENEFITS = {
    SubscriptionPlan.FREE: {
        "listing_limit": 1,
        "analytics_access": False,
        "description": "Basic hotel listing with no analytics access.",
    },
    SubscriptionPlan.BASIC: {
        "listing_limit": 3,
        "analytics_access": True,
        "description": "Up to 3 listings with basic analytics access.",
    },
    SubscriptionPlan.PREMIUM: {
        "listing_limit": 10,
        "analytics_access": True,
        "description": "Up to 10 listings with analytics access.",
    },
    SubscriptionPlan.ENTERPRISE: {
        "listing_limit": None,
        "analytics_access": True,
        "description": "Unlimited listings with analytics access.",
    },
}


def get_subscription_plan_benefits(
    plan: SubscriptionPlan,
) -> dict:
    """Return the benefits configured for a subscription plan."""
    return SUBSCRIPTION_PLAN_BENEFITS[plan]
