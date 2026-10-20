import os

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.audit_log import AuditEventType
from app.services.audit_log_service import record_audit_event
from app.models import (
    Payment,
    PaymentEvent,
    PaymentStatus,
    Reservation,
    ReservationStatus,
    User,
    UserRole,
)
from app.models.notification import Notification
from app.schemas.payment import (
    MockPaymentEventRequest,
    PaymentCheckoutRequest,
    PaymentResponse,
    PaymentSimulationRequest,
)

load_dotenv()

router = APIRouter(prefix="/payments", tags=["Payments"])


def mock_payments_enabled() -> bool:
    """Enable mock payment features only in development."""
    environment = os.getenv("APP_ENV", "development").strip().lower()
    mock_mode = os.getenv(
        "PAYMENTS_MOCK_MODE", "false"
    ).strip().lower()

    return environment == "development" and mock_mode == "true"


def require_mock_mode() -> None:
    if not mock_payments_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mock payment features are disabled.",
        )


def add_payment_notification(
    db: Session,
    payment: Payment,
) -> None:
    """Create an in-app notification for a successful payment."""
    db.add(
        Notification(
            user_id=payment.customer_id,
            title="Payment successful",
            message=(
                f"Your payment of {payment.currency} {payment.amount} "
                f"for reservation #{payment.reservation_id} "
                "was successful."
            ),
            notification_type="payment_succeeded",
            related_reservation_id=payment.reservation_id,
            metadata_json={
                "payment_id": payment.id,
                "reservation_id": payment.reservation_id,
                "amount": str(payment.amount),
                "currency": payment.currency,
            },
        )
    )


@router.post(
    "/checkout",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_payment_checkout(
    payload: PaymentCheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a mock pending payment for a confirmed reservation."""
    if current_user.role != UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403,
            detail="Only customers can create payments.",
        )

    require_mock_mode()

    existing = (
        db.query(Payment)
        .filter(
            Payment.idempotency_key == payload.idempotency_key
        )
        .first()
    )

    if existing is not None:
        if (
            existing.customer_id != current_user.id
            or existing.reservation_id != payload.reservation_id
        ):
            raise HTTPException(
                status_code=409,
                detail="This idempotency key has already been used.",
            )
        return existing

    reservation = (
        db.query(Reservation)
        .filter(
            Reservation.id == payload.reservation_id,
            Reservation.customer_id == current_user.id,
        )
        .first()
    )

    if reservation is None:
        raise HTTPException(
            status_code=404,
            detail="Reservation not found.",
        )

    if reservation.status != ReservationStatus.CONFIRMED:
        raise HTTPException(
            status_code=409,
            detail="Only confirmed reservations can be paid for.",
        )

    if (
        reservation.total_price is None
        or reservation.total_price <= 0
    ):
        raise HTTPException(
            status_code=409,
            detail="Reservation has an invalid payment amount.",
        )

    payment = Payment(
        reservation_id=reservation.id,
        customer_id=current_user.id,
        amount=reservation.total_price,
        currency="inr",
        status=PaymentStatus.PENDING,
        idempotency_key=payload.idempotency_key,
    )

    try:
        db.add(payment)
        db.flush()

        record_audit_event(
            db=db,
            event_type=AuditEventType.PAYMENT_CREATED,
            action="PAYMENT_CREATED",
            actor_id=current_user.id,
            description="Payment checkout was created.",
            entity_type="payment",
            entity_id=payment.id,
            details={
                "reservation_id": payment.reservation_id,
                "amount": str(payment.amount),
                "currency": payment.currency,
                "status": payment.status.value,
            },
            commit=False,
        )

        db.commit()
        db.refresh(payment)

    except IntegrityError:
        db.rollback()

        existing = (
            db.query(Payment)
            .filter(
                Payment.idempotency_key == payload.idempotency_key
            )
            .first()
        )

        if (
            existing is not None
            and existing.customer_id == current_user.id
            and existing.reservation_id == payload.reservation_id
        ):
            return existing

        raise HTTPException(
            status_code=409,
            detail="A payment with this idempotency key already exists.",
        )

    return payment


@router.get("/my", response_model=list[PaymentResponse])
def get_my_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the authenticated customer's payment history."""
    if current_user.role != UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403,
            detail="Only customers can view their payment history.",
        )

    return (
        db.query(Payment)
        .filter(Payment.customer_id == current_user.id)
        .order_by(Payment.created_at.desc())
        .all()
    )


@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve a payment owned by the customer or visible to an admin."""
    payment = (
        db.query(Payment)
        .filter(Payment.id == payment_id)
        .first()
    )

    if payment is None:
        raise HTTPException(
            status_code=404,
            detail="Payment not found.",
        )

    if current_user.role == UserRole.CUSTOMER:
        if payment.customer_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Access denied.",
            )
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Access denied.",
        )

    return payment


@router.post(
    "/{payment_id}/simulate",
    response_model=PaymentResponse,
)
def simulate_payment_result(
    payment_id: int,
    payload: PaymentSimulationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Simulate a successful or failed payment in development."""
    require_mock_mode()

    if current_user.role != UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403,
            detail="Only customers can simulate their payments.",
        )

    if payload.status not in (
        PaymentStatus.SUCCEEDED,
        PaymentStatus.FAILED,
    ):
        raise HTTPException(
            status_code=422,
            detail="Simulation status must be SUCCEEDED or FAILED.",
        )

    payment = (
        db.query(Payment)
        .filter(
            Payment.id == payment_id,
            Payment.customer_id == current_user.id,
        )
        .with_for_update()
        .first()
    )

    if payment is None:
        raise HTTPException(
            status_code=404,
            detail="Payment not found.",
        )

    if payment.status != PaymentStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail="Only pending payments can be simulated.",
        )

    payment.status = payload.status

    if payload.status == PaymentStatus.SUCCEEDED:
        add_payment_notification(db, payment)

    try:
        record_audit_event(
            db=db,
            event_type=(
                AuditEventType.PAYMENT_SUCCEEDED
                if payment.status == PaymentStatus.SUCCEEDED
                else AuditEventType.PAYMENT_FAILED
            ),
            action="PAYMENT_STATUS_SIMULATED",
            actor_id=current_user.id,
            description="Payment result was simulated in development mode.",
            entity_type="payment",
            entity_id=payment.id,
            details={
                "reservation_id": payment.reservation_id,
                "status": payment.status.value,
                "amount": str(payment.amount),
                "currency": payment.currency,
            },
            commit=False,
        )

        db.commit()
        db.refresh(payment)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Payment status could not be updated.",
        )

    return payment


@router.post(
    "/mock-webhook",
    response_model=PaymentResponse,
)
def receive_mock_payment_event(
    payload: MockPaymentEventRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Process a simulated payment event.

    This development-only endpoint does not verify real Stripe signatures.
    Access is restricted to administrators.
    """
    require_mock_mode()

    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only administrators can submit mock payment events.",
        )

    if payload.status not in (
        PaymentStatus.SUCCEEDED,
        PaymentStatus.FAILED,
    ):
        raise HTTPException(
            status_code=422,
            detail="Mock event status must be SUCCEEDED or FAILED.",
        )

    # Record the event before changing the payment status.
    try:
        with db.begin_nested():
            event = PaymentEvent(
                event_id=payload.event_id,
                payment_id=payload.payment_id,
                event_type=f"payment.{payload.status.value.lower()}",
                resulting_status=payload.status.value,
            )
            db.add(event)
            db.flush()

    except IntegrityError:
        # The event ID may already have been processed.
        db.rollback()

        existing_event = (
            db.query(PaymentEvent)
            .filter(PaymentEvent.event_id == payload.event_id)
            .first()
        )

        if existing_event is not None:
            if existing_event.payment_id != payload.payment_id:
                raise HTTPException(
                    status_code=409,
                    detail="This event ID was already used for another payment.",
                )

            payment = (
                db.query(Payment)
                .filter(Payment.id == existing_event.payment_id)
                .first()
            )

            if payment is None:
                raise HTTPException(
                    status_code=404,
                    detail="Payment not found.",
                )

            # Repeated delivery of an existing event is idempotent.
            return payment

        raise HTTPException(
            status_code=409,
            detail="Payment event could not be recorded.",
        )

    payment = (
        db.query(Payment)
        .filter(Payment.id == payload.payment_id)
        .with_for_update()
        .first()
    )

    if payment is None:
        db.rollback()
        raise HTTPException(
            status_code=404,
            detail="Payment not found.",
        )

    if payment.status != PaymentStatus.PENDING:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Only pending payments can receive a new event.",
        )

    payment.status = payload.status
    payment.last_stripe_event_id = payload.event_id

    if payload.status == PaymentStatus.SUCCEEDED:
        add_payment_notification(db, payment)

    try:
        record_audit_event(
            db=db,
            event_type=(
                AuditEventType.PAYMENT_SUCCEEDED
                if payment.status == PaymentStatus.SUCCEEDED
                else AuditEventType.PAYMENT_FAILED
            ),
            action="MOCK_PAYMENT_WEBHOOK_PROCESSED",
            actor_id=current_user.id,
            description="Administrator processed a mock payment event.",
            entity_type="payment",
            entity_id=payment.id,
            details={
                "reservation_id": payment.reservation_id,
                "status": payment.status.value,
                "event_id": payload.event_id,
            },
            commit=False,
        )

        db.commit()
        db.refresh(payment)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Mock payment event could not be processed.",
        )

    return payment