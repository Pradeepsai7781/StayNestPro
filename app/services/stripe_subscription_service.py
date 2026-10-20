
import os

import stripe
from fastapi import HTTPException, status


def get_stripe_client():
    """Configure Stripe using the secret key from .env."""
    secret_key = os.getenv("STRIPE_SECRET_KEY", "").strip()

    if not secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe billing is not configured.",
        )

    stripe.api_key = secret_key
    return stripe


def create_stripe_customer(email: str, hotel_id: int):
    """Create a Stripe customer for a hotel subscription."""
    stripe_client = get_stripe_client()

    try:
        return stripe_client.Customer.create(
            email=email,
            metadata={"hotel_id": str(hotel_id)},
        )
    except stripe.StripeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to create Stripe customer.",
        ) from exc


def create_subscription_checkout_session(
    customer_id: str,
    price_id: str,
    success_url: str,
    cancel_url: str,
    hotel_id: int,
):
    """Create a Stripe Checkout Session for recurring subscription billing."""
    stripe_client = get_stripe_client()

    try:
        return stripe_client.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"hotel_id": str(hotel_id)},
            subscription_data={
                "metadata": {"hotel_id": str(hotel_id)}
            },
        )
    except stripe.StripeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to create Stripe checkout session.",
        ) from exc


def change_stripe_subscription_plan(
    stripe_subscription_id: str,
    price_id: str,
):
    """Change the price on an existing Stripe subscription."""
    stripe_client = get_stripe_client()

    try:
        subscription = stripe_client.Subscription.retrieve(
            stripe_subscription_id
        )

        items = subscription["items"]["data"]
        if not items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stripe subscription has no subscription items.",
            )

        item_id = items[0]["id"]

        return stripe_client.Subscription.modify(
            stripe_subscription_id,
            items=[
                {
                    "id": item_id,
                    "price": price_id,
                }
            ],
            proration_behavior="create_prorations",
        )
    except stripe.StripeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to update Stripe subscription.",
        ) from exc


def cancel_stripe_subscription(stripe_subscription_id: str):
    """Schedule cancellation at the end of the billing period."""
    stripe_client = get_stripe_client()

    try:
        return stripe_client.Subscription.modify(
            stripe_subscription_id,
            cancel_at_period_end=True,
        )
    except stripe.StripeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to cancel Stripe subscription.",
        ) from exc
