
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.loyalty import (
    LoyaltyAccount,
    LoyaltyEntryType,
    LoyaltyLedgerEntry,
)
from app.models.payment import Payment, PaymentStatus
from app.models.reservation import Reservation, ReservationStatus


POINTS_PER_HUNDRED = 10
RUPEES_PER_POINT = Decimal("1.00")


def get_or_create_loyalty_account(
    db: Session,
    user_id: int,
) -> LoyaltyAccount:
    account = db.scalar(
        select(LoyaltyAccount)
        .where(LoyaltyAccount.user_id == user_id)
        .with_for_update()
    )

    if account is not None:
        return account

    account = LoyaltyAccount(user_id=user_id)

    try:
        with db.begin_nested():
            db.add(account)
            db.flush()
        return account

    except IntegrityError:
        account = db.scalar(
            select(LoyaltyAccount)
            .where(LoyaltyAccount.user_id == user_id)
            .with_for_update()
        )

        if account is not None:
            return account

        raise


def update_membership_tier(
    db: Session,
    account: LoyaltyAccount,
) -> None:
    entries = db.scalars(
        select(LoyaltyLedgerEntry).where(
            LoyaltyLedgerEntry.user_id == account.user_id,
            LoyaltyLedgerEntry.points > 0,
        )
    ).all()

    lifetime_points = sum(entry.points for entry in entries)

    if lifetime_points >= 5000:
        account.membership_tier = "GOLD"
    elif lifetime_points >= 2000:
        account.membership_tier = "SILVER"
    else:
        account.membership_tier = "BRONZE"


def award_booking_points(
    db: Session,
    reservation: Reservation,
    user_id: int,
) -> LoyaltyLedgerEntry | None:
    if reservation.customer_id != user_id:
        raise PermissionError(
            "You cannot receive points for another user's booking."
        )

    if reservation.status != ReservationStatus.COMPLETED:
        raise ValueError(
            "Points can only be awarded for completed bookings."
        )

    payment = db.scalar(
        select(Payment)
        .where(
            Payment.reservation_id == reservation.id,
            Payment.customer_id == user_id,
            Payment.status == PaymentStatus.SUCCEEDED,
        )
        .with_for_update()
    )

    if payment is None:
        raise ValueError(
            "A successful payment is required to earn loyalty points."
        )

    idempotency_key = f"booking-reward:{reservation.id}"

    existing = db.scalar(
        select(LoyaltyLedgerEntry).where(
            LoyaltyLedgerEntry.idempotency_key == idempotency_key
        )
    )

    if existing is not None:
        return existing

    amount = Decimal(str(payment.amount))
    points = (
        int(
            (amount / Decimal("100")).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )
        * POINTS_PER_HUNDRED
    )

    if points <= 0:
        return None

    account = get_or_create_loyalty_account(db, user_id)
    account.points_balance += points

    entry = LoyaltyLedgerEntry(
        user_id=user_id,
        reservation_id=reservation.id,
        entry_type=LoyaltyEntryType.BOOKING_REWARD,
        points=points,
        idempotency_key=idempotency_key,
        description=(
            f"Points awarded for completed booking #{reservation.id}"
        ),
    )

    db.add(entry)
    db.flush()

    update_membership_tier(db, account)

    return entry


def redeem_points(
    db: Session,
    user_id: int,
    payment_id: int,
    points: int,
) -> LoyaltyLedgerEntry:
    if points <= 0:
        raise ValueError(
            "Points to redeem must be greater than zero."
        )

    payment = db.scalar(
        select(Payment)
        .where(
            Payment.id == payment_id,
            Payment.customer_id == user_id,
        )
        .with_for_update()
    )

    if payment is None:
        raise PermissionError(
            "Payment not found or does not belong to you."
        )

    if payment.status != PaymentStatus.PENDING:
        raise ValueError(
            "Points can only be redeemed before payment succeeds."
        )

    if payment.stripe_checkout_session_id is not None:
        raise ValueError(
            "Checkout has already been created. Points cannot be redeemed "
            "after checkout creation."
        )

    reservation = db.scalar(
        select(Reservation)
        .where(
            Reservation.id == payment.reservation_id,
            Reservation.customer_id == user_id,
            Reservation.status == ReservationStatus.CONFIRMED,
        )
        .with_for_update()
    )

    if reservation is None:
        raise ValueError(
            "Points can only be redeemed for your confirmed reservation."
        )

    idempotency_key = f"redemption:{payment_id}"

    existing = db.scalar(
        select(LoyaltyLedgerEntry).where(
            LoyaltyLedgerEntry.idempotency_key == idempotency_key
        )
    )

    if existing is not None:
        raise ValueError(
            "Points have already been redeemed for this payment."
        )

    account = db.scalar(
        select(LoyaltyAccount)
        .where(LoyaltyAccount.user_id == user_id)
        .with_for_update()
    )

    if account is None:
        raise ValueError(
            "A loyalty account is required before redeeming points."
        )

    if account.points_balance < points:
        raise ValueError("Insufficient loyalty points.")

    current_amount = Decimal(str(payment.amount))
    discount = RUPEES_PER_POINT * points

    if discount >= current_amount:
        raise ValueError(
            "Redemption must leave a positive payment amount."
        )

    account.points_balance -= points
    payment.amount = current_amount - discount

    entry = LoyaltyLedgerEntry(
        user_id=user_id,
        reservation_id=reservation.id,
        payment_id=payment.id,
        entry_type=LoyaltyEntryType.REDEMPTION,
        points=-points,
        monetary_value=discount,
        idempotency_key=idempotency_key,
        description=(
            f"Redeemed {points} points against payment #{payment.id}"
        ),
    )

    db.add(entry)
    db.flush()

    return entry
