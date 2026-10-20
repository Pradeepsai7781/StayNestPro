
import os
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.hotel import Hotel
from app.models.notification import Notification
from app.models.payment import Payment, PaymentStatus
from app.models.refund import Refund, RefundStatus
from app.models.reservation import Reservation, ReservationStatus
from app.models.room import Room
from app.models.user import User, UserRole
from app.schemas.refund import (
    RefundRequestCreate,
    RefundReviewRequest,
    RefundResponse,
)

load_dotenv()

router = APIRouter(prefix="/refunds", tags=["Refunds"])


def mock_refunds_enabled() -> bool:
    return (
        os.getenv("APP_ENV", "development").lower() == "development"
        and os.getenv("PAYMENTS_MOCK_MODE", "false").lower() == "true"
    )


def get_reservation_hotel(
    reservation: Reservation,
    db: Session,
) -> Hotel:
    room = db.scalar(
        select(Room).where(Room.id == reservation.room_id)
    )

    if room is None:
        raise HTTPException(
            status_code=404,
            detail="Reservation room not found.",
        )

    hotel = db.scalar(
        select(Hotel).where(Hotel.id == room.hotel_id)
    )

    if hotel is None:
        raise HTTPException(
            status_code=404,
            detail="Hotel not found.",
        )

    return hotel


def calculate_refund_amount(
    reservation: Reservation,
    hotel: Hotel,
) -> Decimal:
    policies = hotel.policies or {}
    check_in = reservation.check_in

    if isinstance(check_in, datetime):
        check_in = check_in.date()

    days_before_checkin = (check_in - date.today()).days

    cancellation_text = str(
        policies.get("cancellation", "")
    ).lower()

    if "24 hours" in cancellation_text:
        if days_before_checkin >= 1:
            return Decimal(
                str(reservation.total_price)
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )

        return Decimal("0.00")

    free_days = policies.get("cancellation_free_days")
    refund_percentage = policies.get(
        "cancellation_refund_percentage",
        0,
    )

    if (
        free_days is not None
        and days_before_checkin >= int(free_days)
    ):
        refund_percentage = 100

    amount = (
        Decimal(str(reservation.total_price))
        * Decimal(str(refund_percentage))
        / Decimal("100")
    )

    return amount.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


@router.post(
    "",
    response_model=RefundResponse,
    status_code=201,
)
def request_refund(
    payload: RefundRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403,
            detail="Only customers can request refunds.",
        )

    payment = db.scalar(
        select(Payment).where(
            Payment.id == payload.payment_id,
            Payment.customer_id == current_user.id,
        )
    )

    if payment is None:
        raise HTTPException(
            status_code=404,
            detail="Payment not found.",
        )

    if payment.status != PaymentStatus.SUCCEEDED:
        raise HTTPException(
            status_code=409,
            detail="Only successful payments can be refunded.",
        )

    reservation = db.scalar(
        select(Reservation).where(
            Reservation.id == payment.reservation_id,
            Reservation.customer_id == current_user.id,
        )
    )

    if reservation is None:
        raise HTTPException(
            status_code=404,
            detail="Reservation not found.",
        )

    if reservation.status == ReservationStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail="Completed reservations cannot be refunded.",
        )

    existing_refund = db.scalar(
        select(Refund).where(
            Refund.payment_id == payment.id,
            Refund.status.in_(
                [
                    RefundStatus.PENDING,
                    RefundStatus.APPROVED,
                    RefundStatus.PROCESSING,
                    RefundStatus.SUCCEEDED,
                ]
            ),
        )
    )

    if existing_refund is not None:
        raise HTTPException(
            status_code=409,
            detail="A refund request already exists for this payment.",
        )

    hotel = get_reservation_hotel(reservation, db)

    refund_amount = calculate_refund_amount(
        reservation,
        hotel,
    )

    if refund_amount <= Decimal("0.00"):
        raise HTTPException(
            status_code=409,
            detail="The cancellation policy does not allow a refund.",
        )

    refund = Refund(
        payment_id=payment.id,
        reservation_id=reservation.id,
        customer_id=current_user.id,
        amount=refund_amount,
        currency=payment.currency,
        status=RefundStatus.PENDING,
        reason=payload.reason.strip(),
    )

    db.add(refund)
    db.commit()
    db.refresh(refund)

    return refund


@router.get(
    "/my",
    response_model=list[RefundResponse],
)
def get_my_refunds(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403,
            detail="Only customers can view their refund history.",
        )

    refunds = db.scalars(
        select(Refund)
        .where(Refund.customer_id == current_user.id)
        .order_by(Refund.created_at.desc())
    ).all()

    return list(refunds)


@router.get(
    "/{refund_id}",
    response_model=RefundResponse,
)
def get_refund(
    refund_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    refund = db.get(Refund, refund_id)

    if refund is None:
        raise HTTPException(
            status_code=404,
            detail="Refund not found.",
        )

    is_admin = current_user.role == UserRole.ADMIN
    is_owner = refund.customer_id == current_user.id

    if not is_admin and not is_owner:
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to view this refund.",
        )

    return refund


@router.patch(
    "/{refund_id}/review",
    response_model=RefundResponse,
)
def review_refund(
    refund_id: int,
    payload: RefundReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only administrators can review refund requests.",
        )

    if payload.status not in (
        RefundStatus.APPROVED,
        RefundStatus.REJECTED,
    ):
        raise HTTPException(
            status_code=422,
            detail="Review status must be APPROVED or REJECTED.",
        )

    refund = db.scalar(
        select(Refund)
        .where(Refund.id == refund_id)
        .with_for_update()
    )

    if refund is None:
        raise HTTPException(
            status_code=404,
            detail="Refund not found.",
        )

    if refund.status != RefundStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail="Only pending refunds can be reviewed.",
        )

    refund.status = payload.status
    refund.reviewed_by = current_user.id
    refund.review_note = (
        payload.review_note.strip()
        if payload.review_note
        else None
    )

    db.commit()
    db.refresh(refund)

    return refund


@router.post(
    "/{refund_id}/process",
    response_model=RefundResponse,
)
def process_refund(
    refund_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Only administrators can process refunds.",
        )

    refund = db.scalar(
        select(Refund)
        .where(Refund.id == refund_id)
        .with_for_update()
    )

    if refund is None:
        raise HTTPException(
            status_code=404,
            detail="Refund not found.",
        )

    if refund.status != RefundStatus.APPROVED:
        raise HTTPException(
            status_code=409,
            detail="Only approved refunds can be processed.",
        )

    if not mock_refunds_enabled():
        raise HTTPException(
            status_code=503,
            detail="Real Stripe refund processing is not configured.",
        )

    # Development-only simulation; this does not transfer money.
    refund.status = RefundStatus.SUCCEEDED

    db.add(
        Notification(
            user_id=refund.customer_id,
            title="Refund successful",
            message=(
                f"Your refund of {refund.currency} {refund.amount} "
                f"for reservation #{refund.reservation_id} "
                "has been processed successfully."
            ),
            notification_type="refund_succeeded",
            related_reservation_id=refund.reservation_id,
            metadata_json={
                "refund_id": refund.id,
                "payment_id": refund.payment_id,
                "reservation_id": refund.reservation_id,
                "amount": str(refund.amount),
                "currency": refund.currency,
            },
        )
    )

    db.commit()
    db.refresh(refund)

    return refund
