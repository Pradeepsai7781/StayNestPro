
import os
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import HotelSubscription
from app.models.hotel_subscription import SubscriptionStatus
from app.models.subscription_payment import (
    SubscriptionPayment,
    SubscriptionPaymentStatus,
)

router = APIRouter(
    prefix="/subscription-webhooks",
    tags=["Subscription Payments"],
)


@router.post("/stripe")
async def stripe_subscription_webhook(
    request: Request,
    stripe_signature: str | None = Header(
        default=None,
        alias="Stripe-Signature",
    ),
    db: Session = Depends(get_db),
):
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()

    if not webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhook is not configured.",
        )

    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header.",
        )

    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload,
            stripe_signature,
            webhook_secret,
        )
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe webhook payload or signature.",
        ) from exc

    event_type = event["type"]
    event_object = event["data"]["object"]

    try:
        if event_type in (
            "invoice.payment_succeeded",
            "invoice.payment_failed",
        ):
            invoice_id = event_object.get("id")
            payment_intent_id = event_object.get("payment_intent")
            stripe_subscription_id = event_object.get("subscription")

            subscription = None

            if stripe_subscription_id:
                subscription = (
                    db.query(HotelSubscription)
                    .filter(
                        HotelSubscription.stripe_subscription_id
                        == stripe_subscription_id
                    )
                    .first()
                )

            if subscription is not None and invoice_id:
                payment = (
                    db.query(SubscriptionPayment)
                    .filter(
                        SubscriptionPayment.stripe_invoice_id == invoice_id
                    )
                    .first()
                )

                payment_status = (
                    SubscriptionPaymentStatus.SUCCEEDED
                    if event_type == "invoice.payment_succeeded"
                    else SubscriptionPaymentStatus.FAILED
                )

                amount_minor_units = (
                    event_object.get("amount_paid", 0)
                    if event_type == "invoice.payment_succeeded"
                    else event_object.get("amount_due", 0)
                )

                # Stripe sends invoice amounts in the currency's minor unit.
                amount = amount_minor_units / 100

                if payment is None:
                    payment = SubscriptionPayment(
                        hotel_subscription_id=subscription.id,
                        stripe_invoice_id=invoice_id,
                        stripe_payment_intent_id=payment_intent_id,
                        amount=amount,
                        currency=event_object.get("currency", "usd"),
                        status=payment_status,
                    )
                    db.add(payment)
                else:
                    payment.status = payment_status
                    payment.amount = amount
                    payment.currency = event_object.get(
                        "currency", "usd"
                    )
                    if payment_intent_id:
                        payment.stripe_payment_intent_id = (
                            payment_intent_id
                        )

                db.commit()

        elif event_type in (
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
        ):
            stripe_subscription_id = event_object.get("id")
            stripe_customer_id = event_object.get("customer")

            subscription = (
                db.query(HotelSubscription)
                .filter(
                    HotelSubscription.stripe_subscription_id
                    == stripe_subscription_id
                )
                .first()
            )

            # On initial creation, Stripe metadata links the event to a hotel.
            if subscription is None:
                metadata = event_object.get("metadata") or {}
                hotel_id = metadata.get("hotel_id")

                if hotel_id:
                    subscription = (
                        db.query(HotelSubscription)
                        .filter(
                            HotelSubscription.hotel_id == int(hotel_id)
                        )
                        .first()
                    )

            if subscription is not None:
                subscription.stripe_subscription_id = (
                    stripe_subscription_id
                )
                subscription.stripe_customer_id = stripe_customer_id

                stripe_status = event_object.get("status")

                if event_type == "customer.subscription.deleted":
                    subscription.status = SubscriptionStatus.CANCELLED
                elif stripe_status == "active":
                    subscription.status = SubscriptionStatus.ACTIVE
                elif stripe_status in (
                    "canceled",
                    "unpaid",
                    "incomplete_expired",
                ):
                    subscription.status = SubscriptionStatus.CANCELLED
                elif stripe_status == "past_due":
                    subscription.status = SubscriptionStatus.EXPIRED

                period_end = event_object.get("current_period_end")

                if period_end:
                    subscription.expires_at = datetime.fromtimestamp(
                        period_end,
                        tz=timezone.utc,
                    )

                db.commit()

    except Exception:
        db.rollback()
        raise

    return {"received": True}
