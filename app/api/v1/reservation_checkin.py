
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import (
    Hotel,
    Payment,
    PaymentStatus,
    Reservation,
    ReservationStatus,
    ReservationStay,
    Room,
    RoomStatus,
    User,
    UserRole,
)
from app.schemas.reservation_stay import (
    CheckInRequest,
    CheckOutRequest,
    ReservationStayResponse,
    RoomAssignmentRequest,
)

router = APIRouter(
    prefix="/reservations",
    tags=["Reservation Check-In/Check-Out"],
)


def get_authorized_reservation(
    reservation_id: int,
    db: Session,
    user: User,
) -> Reservation:
    reservation = (
        db.query(Reservation)
        .filter(Reservation.id == reservation_id)
        .first()
    )

    if reservation is None:
        raise HTTPException(
            status_code=404,
            detail="Reservation not found.",
        )

    if user.role == UserRole.CUSTOMER:
        if reservation.customer_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="Access denied.",
            )

    elif user.role == UserRole.HOTEL_OWNER:
        room = (
            db.query(Room)
            .filter(Room.id == reservation.room_id)
            .first()
        )

        hotel = (
            db.query(Hotel)
            .filter(Hotel.id == room.hotel_id)
            .first()
            if room
            else None
        )

        if hotel is None or hotel.owner_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="Access denied.",
            )

    elif user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Access denied.",
        )

    return reservation


def get_stay(
    reservation_id: int,
    db: Session,
) -> ReservationStay:
    stay = (
        db.query(ReservationStay)
        .filter(
            ReservationStay.reservation_id == reservation_id
        )
        .first()
    )

    if stay is None:
        stay = ReservationStay(
            reservation_id=reservation_id,
            early_check_in_charge=Decimal("0.00"),
            late_check_out_charge=Decimal("0.00"),
        )
        db.add(stay)
        db.flush()

    return stay


def validate_payment(
    reservation: Reservation,
    db: Session,
) -> None:
    payment = (
        db.query(Payment)
        .filter(
            Payment.reservation_id == reservation.id,
            Payment.customer_id == reservation.customer_id,
            Payment.status == PaymentStatus.SUCCEEDED,
        )
        .order_by(Payment.id.desc())
        .first()
    )

    if payment is None:
        raise HTTPException(
            status_code=409,
            detail="A successful payment is required before check-in.",
        )

    if (
        reservation.total_price is None
        or payment.amount < reservation.total_price
    ):
        raise HTTPException(
            status_code=409,
            detail="Successful payment does not cover the reservation amount.",
        )


def validate_charge(amount: Decimal, charge_name: str) -> None:
    if not amount.is_finite() or amount < Decimal("0.00"):
        raise HTTPException(
            status_code=422,
            detail=f"{charge_name} must be a valid non-negative amount.",
        )


@router.get(
    "/{reservation_id}/stay",
    response_model=ReservationStayResponse,
)
def verify_reservation_stay(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reservation = get_authorized_reservation(
        reservation_id, db, current_user
    )

    stay = (
        db.query(ReservationStay)
        .filter(
            ReservationStay.reservation_id == reservation.id
        )
        .first()
    )

    if stay is None:
        raise HTTPException(
            status_code=404,
            detail="Check-in/check-out record has not been created yet.",
        )

    return stay


@router.patch("/{reservation_id}/assign-room")
def assign_room(
    reservation_id: int,
    payload: RoomAssignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (
        UserRole.ADMIN,
        UserRole.HOTEL_OWNER,
    ):
        raise HTTPException(
            status_code=403,
            detail="Only administrators or hotel owners can assign rooms.",
        )

    reservation = get_authorized_reservation(
        reservation_id, db, current_user
    )

    if reservation.status != ReservationStatus.CONFIRMED:
        raise HTTPException(
            status_code=409,
            detail="Only confirmed reservations can be assigned.",
        )

    stay = (
        db.query(ReservationStay)
        .filter(
            ReservationStay.reservation_id == reservation.id
        )
        .first()
    )

    if stay and stay.actual_check_in is not None:
        raise HTTPException(
            status_code=409,
            detail="Room cannot be reassigned after check-in.",
        )

    room = (
        db.query(Room)
        .filter(Room.id == payload.room_id)
        .first()
    )

    if room is None:
        raise HTTPException(
            status_code=404,
            detail="Room not found.",
        )

    current_room = (
        db.query(Room)
        .filter(Room.id == reservation.room_id)
        .first()
    )

    if (
        current_room is None
        or room.hotel_id != current_room.hotel_id
    ):
        raise HTTPException(
            status_code=409,
            detail="Room must belong to the reservation's hotel.",
        )

    hotel = (
        db.query(Hotel)
        .filter(Hotel.id == room.hotel_id)
        .first()
    )

    if (
        current_user.role == UserRole.HOTEL_OWNER
        and (hotel is None or hotel.owner_id != current_user.id)
    ):
        raise HTTPException(
            status_code=403,
            detail="Access denied.",
        )

    if room.status != RoomStatus.AVAILABLE:
        raise HTTPException(
            status_code=409,
            detail="Room is not available.",
        )

    conflict = (
        db.query(Reservation.id)
        .filter(
            Reservation.room_id == room.id,
            Reservation.id != reservation.id,
            Reservation.status == ReservationStatus.CONFIRMED,
            Reservation.check_in < reservation.check_out,
            Reservation.check_out > reservation.check_in,
        )
        .first()
    )

    if conflict:
        raise HTTPException(
            status_code=409,
            detail="Room conflicts with another reservation.",
        )

    reservation.room_id = room.id

    try:
        db.commit()
        db.refresh(reservation)
    except Exception:
        db.rollback()
        raise

    return {
        "message": "Room assigned successfully.",
        "reservation_id": reservation.id,
        "room_id": room.id,
    }


@router.post(
    "/{reservation_id}/check-in",
    response_model=ReservationStayResponse,
)
def check_in_guest(
    reservation_id: int,
    payload: CheckInRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (
        UserRole.ADMIN,
        UserRole.HOTEL_OWNER,
    ):
        raise HTTPException(
            status_code=403,
            detail="Only administrators or hotel owners can check in guests.",
        )

    reservation = get_authorized_reservation(
        reservation_id, db, current_user
    )

    if reservation.status != ReservationStatus.CONFIRMED:
        raise HTTPException(
            status_code=409,
            detail="Reservation is not confirmed.",
        )

    validate_charge(
        payload.early_check_in_charge,
        "Early check-in charge",
    )

    now = datetime.now(timezone.utc)

    if now.date() < reservation.check_in:
        if payload.early_check_in_charge <= Decimal("0.00"):
            raise HTTPException(
                status_code=409,
                detail="Early check-in requires a positive early check-in charge.",
            )

    room = (
        db.query(Room)
        .filter(Room.id == reservation.room_id)
        .first()
    )

    if room is None:
        raise HTTPException(
            status_code=404,
            detail="Assigned room not found.",
        )

    hotel = (
        db.query(Hotel)
        .filter(Hotel.id == room.hotel_id)
        .first()
    )

    if (
        current_user.role == UserRole.HOTEL_OWNER
        and (hotel is None or hotel.owner_id != current_user.id)
    ):
        raise HTTPException(
            status_code=403,
            detail="Access denied.",
        )

    if room.status not in (
        RoomStatus.AVAILABLE,
        RoomStatus.CLEAN,
    ):
        raise HTTPException(
            status_code=409,
            detail="Assigned room is not ready.",
        )

    validate_payment(reservation, db)

    stay = get_stay(reservation.id, db)

    if stay.actual_check_in is not None:
        raise HTTPException(
            status_code=409,
            detail="Guest is already checked in.",
        )

    stay.actual_check_in = now
    stay.early_check_in_charge = payload.early_check_in_charge
    room.status = RoomStatus.OCCUPIED

    try:
        db.commit()
        db.refresh(stay)
    except Exception:
        db.rollback()
        raise

    return stay


@router.post(
    "/{reservation_id}/check-out",
    response_model=ReservationStayResponse,
)
def check_out_guest(
    reservation_id: int,
    payload: CheckOutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (
        UserRole.ADMIN,
        UserRole.HOTEL_OWNER,
    ):
        raise HTTPException(
            status_code=403,
            detail="Only administrators or hotel owners can check out guests.",
        )

    reservation = get_authorized_reservation(
        reservation_id, db, current_user
    )

    stay = (
        db.query(ReservationStay)
        .filter(
            ReservationStay.reservation_id == reservation.id
        )
        .first()
    )

    if stay is None or stay.actual_check_in is None:
        raise HTTPException(
            status_code=409,
            detail="Guest must check in before checking out.",
        )

    if stay.actual_check_out is not None:
        raise HTTPException(
            status_code=409,
            detail="Guest is already checked out.",
        )

    now = datetime.now(timezone.utc)

    validate_charge(
        payload.late_check_out_charge,
        "Late check-out charge",
    )

    if now.date() > reservation.check_out:
        if payload.late_check_out_charge <= Decimal("0.00"):
            raise HTTPException(
                status_code=409,
                detail="Late check-out requires a positive late check-out charge.",
            )

    room = (
        db.query(Room)
        .filter(Room.id == reservation.room_id)
        .first()
    )

    hotel = (
        db.query(Hotel)
        .filter(Hotel.id == room.hotel_id)
        .first()
        if room
        else None
    )

    if (
        current_user.role == UserRole.HOTEL_OWNER
        and (hotel is None or hotel.owner_id != current_user.id)
    ):
        raise HTTPException(
            status_code=403,
            detail="Access denied.",
        )

    stay.actual_check_out = now
    stay.late_check_out_charge = payload.late_check_out_charge

    if room is not None:
        room.status = RoomStatus.DIRTY

    reservation.status = ReservationStatus.COMPLETED

    try:
        db.commit()
        db.refresh(stay)
    except Exception:
        db.rollback()
        raise

    return stay
