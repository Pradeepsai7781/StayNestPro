from datetime import date, datetime, timezone

from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Query, status

from sqlalchemy.exc import IntegrityError

from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user

from app.db.session import get_db

from app.models import (

    Hotel,

    HotelStatus,

    Reservation,

    ReservationStatus,

    Room,

    RoomStatus,

    RoomType,

    User,

    UserRole,

    Notification,

)

from app.models.audit_log import AuditEventType

from app.services.audit_log_service import record_audit_event

from app.models.coupon import Coupon, CouponType

from app.models.coupon_usage import CouponUsage

from app.schemas.reservation import (

    ReservationCancelResponse,

    ReservationCreate,

    ReservationModify,

    ReservationResponse,

    ReservationStatusUpdate,

)

from app.services.dynamic_pricing_service import calculate_room_price

from app.services.loyalty_service import award_booking_points

router = APIRouter(prefix="/reservations", tags=["Reservations"])

def validate_booking_dates(check_in: date, check_out: date) -> int:

    if check_in < date.today():

        raise HTTPException(

            status_code=422,

            detail="Check-in date cannot be in the past.",

        )

    if check_out <= check_in:

        raise HTTPException(

            status_code=422,

            detail="Check-out must be after check-in.",

        )

    return (check_out - check_in).days

def check_room_availability(

    room_id: int,

    check_in: date,

    check_out: date,

    db: Session,

) -> Room:

    room = db.query(Room).filter(Room.id == room_id).first()

    if room is None:

        raise HTTPException(status_code=404, detail="Room not found.")

    if room.status != RoomStatus.AVAILABLE:

        raise HTTPException(

            status_code=409,

            detail="Room is not available for booking.",

        )

    conflict = (

        db.query(Reservation.id)

        .filter(

            Reservation.room_id == room_id,

            Reservation.status == ReservationStatus.CONFIRMED,

            Reservation.check_in < check_out,

            Reservation.check_out > check_in,

        )

        .first()

    )

    if conflict:

        raise HTTPException(

            status_code=409,

            detail="Room is already booked for the selected dates.",

        )

    return room

def get_reservation_for_customer(

    reservation_id: int,

    db: Session,

    current_user: User,

) -> Reservation:

    reservation = (

        db.query(Reservation)

        .filter(

            Reservation.id == reservation_id,

            Reservation.customer_id == current_user.id,

        )

        .first()

    )

    if reservation is None:

        raise HTTPException(

            status_code=404,

            detail="Reservation not found.",

        )

    return reservation

def calculate_total_price(

    price_per_night: Decimal,

    nights: int,

) -> Decimal:

    return (

        Decimal(str(price_per_night)) * Decimal(nights)

    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def calculate_coupon_discount(

    coupon: Coupon,

    booking_amount: Decimal,

) -> Decimal:

    if coupon.coupon_type == CouponType.PERCENTAGE:

        discount = (

            booking_amount

            * Decimal(str(coupon.discount_value))

            / Decimal("100")

        )

    else:

        discount = Decimal(str(coupon.discount_value))

    return min(discount, booking_amount).quantize(

        Decimal("0.01"),

        rounding=ROUND_HALF_UP,

    )

def validate_coupon_for_booking(

    coupon: Coupon,

    user_id: int,

    booking_amount: Decimal,

    check_in: date,

    db: Session,

) -> None:

    if not coupon.is_active:

        raise HTTPException(

            status_code=400,

            detail="Coupon is inactive.",

        )

    now = datetime.now(timezone.utc)

    valid_from = coupon.valid_from

    expires_at = coupon.expires_at

    # MySQL may return naive datetimes.

    if valid_from.tzinfo is None:

        valid_from = valid_from.replace(tzinfo=timezone.utc)

    if expires_at.tzinfo is None:

        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now < valid_from or now > expires_at:

        raise HTTPException(

            status_code=400,

            detail="Coupon is not currently valid.",

        )

    if (

        coupon.usage_limit is not None

        and coupon.used_count >= coupon.usage_limit

    ):

        raise HTTPException(

            status_code=400,

            detail="Coupon usage limit has been reached.",

        )

    if booking_amount < coupon.min_booking_amount:

        raise HTTPException(

            status_code=400,

            detail=f"Minimum booking amount is {coupon.min_booking_amount}.",

        )

    existing_usage = (

        db.query(CouponUsage)

        .filter(

            CouponUsage.coupon_id == coupon.id,

            CouponUsage.user_id == user_id,

        )

        .first()

    )

    if existing_usage:

        raise HTTPException(

            status_code=409,

            detail="You have already used this coupon.",

        )

    # Current default: seasonal coupons apply June through August.

    if coupon.is_seasonal and not (6 <= check_in.month <= 8):

        raise HTTPException(

            status_code=400,

            detail="This seasonal coupon is valid only for June through August.",

        )

    # Current default: early booking requires seven days' notice.

    days_until_checkin = (check_in - date.today()).days

    if coupon.is_early_booking and days_until_checkin < 7:

        raise HTTPException(

            status_code=400,

            detail="This coupon requires booking at least 7 days in advance.",

        )

@router.post(

    "",

    response_model=ReservationResponse,

    status_code=status.HTTP_201_CREATED,

)

def create_reservation(

    payload: ReservationCreate,

    db: Session = Depends(get_db),

    current_user: User = Depends(get_current_user),

):

    if current_user.role != UserRole.CUSTOMER:

        raise HTTPException(

            status_code=403,

            detail="Only customers can create reservations.",

        )

    validate_booking_dates(payload.check_in, payload.check_out)

    room = check_room_availability(

        room_id=payload.room_id,

        check_in=payload.check_in,

        check_out=payload.check_out,

        db=db,

    )

    room_type = (

        db.query(RoomType)

        .filter(

            RoomType.id == room.room_type_id,

            RoomType.hotel_id == room.hotel_id,

        )

        .first()

    )

    if room_type is None:

        raise HTTPException(

            status_code=409,

            detail="The room does not have a valid room type.",

        )

    if payload.guest_count > min(room.capacity, room_type.capacity):

        raise HTTPException(

            status_code=422,

            detail="Guest count exceeds the room capacity.",

        )

    hotel = db.query(Hotel).filter(Hotel.id == room.hotel_id).first()

    if hotel is None or hotel.status != HotelStatus.APPROVED:

        raise HTTPException(

            status_code=409,

            detail="Reservations are allowed only at approved hotels.",

        )

    pricing = calculate_room_price(

        db=db,

        room_id=room.id,

        check_in=payload.check_in,

        check_out=payload.check_out,

    )

    original_amount = pricing["total_price"]

    final_amount = original_amount

    coupon = None

    discount_amount = Decimal("0.00")

    if payload.coupon_code:

        code = payload.coupon_code.strip().upper()

        # Lock the coupon row while validating and applying its usage.

        coupon = (

            db.query(Coupon)

            .filter(Coupon.code == code)

            .with_for_update()

            .first()

        )

        if coupon is None:

            raise HTTPException(

                status_code=404,

                detail="Coupon not found.",

            )

        validate_coupon_for_booking(

            coupon=coupon,

            user_id=current_user.id,

            booking_amount=original_amount,

            check_in=payload.check_in,

            db=db,

        )

        discount_amount = calculate_coupon_discount(

            coupon,

            original_amount,

        )

        final_amount = (

            original_amount - discount_amount

        ).quantize(

            Decimal("0.01"),

            rounding=ROUND_HALF_UP,

        )

    reservation = Reservation(

        room_id=room.id,

        customer_id=current_user.id,

        check_in=payload.check_in,

        check_out=payload.check_out,

        guest_count=payload.guest_count,

        total_price=final_amount,

        status=ReservationStatus.CONFIRMED,

    )

    try:

        db.add(reservation)

        db.flush()

        if coupon is not None:

            db.add(

                CouponUsage(

                    coupon_id=coupon.id,

                    user_id=current_user.id,

                    reservation_id=reservation.id,

                )

            )

            coupon.used_count += 1

        # Module 24: notify the customer about the confirmed booking.

        db.add(

            Notification(

                user_id=current_user.id,

                title="Booking confirmed",

                message=(

                    f"Your reservation #{reservation.id} has been confirmed. "

                    f"Check-in: {reservation.check_in}; "

                    f"check-out: {reservation.check_out}."

                ),

                notification_type="booking_confirmed",

                related_reservation_id=reservation.id,

                metadata_json={

                    "reservation_id": reservation.id,

                    "room_id": reservation.room_id,

                    "hotel_id": room.hotel_id,

                    "check_in": reservation.check_in.isoformat(),

                    "check_out": reservation.check_out.isoformat(),

                },

            )

        )

        record_audit_event(

            db=db,

            event_type=AuditEventType.BOOKING_CREATED,

            action="BOOKING_CREATED",

            actor_id=current_user.id,

            description="Customer created a reservation.",

            entity_type="reservation",

            entity_id=reservation.id,

            details={

                "room_id": reservation.room_id,

                "check_in": reservation.check_in.isoformat(),

                "check_out": reservation.check_out.isoformat(),

                "total_price": str(reservation.total_price),

            },

            commit=False,

        )

        db.commit()

        db.refresh(reservation)

    except IntegrityError:

        db.rollback()

        raise HTTPException(

            status_code=409,

            detail=(

                "Booking could not be completed. "

                "The coupon may already have been used, "

                "or a conflicting record exists."

            ),

        )

    return reservation

@router.get(

    "/my",

    response_model=list[ReservationResponse],

)

def get_my_reservations(

    db: Session = Depends(get_db),

    current_user: User = Depends(get_current_user),

):

    if current_user.role != UserRole.CUSTOMER:

        raise HTTPException(

            status_code=403,

            detail="Only customers can view booking history.",

        )

    return (

        db.query(Reservation)

        .filter(Reservation.customer_id == current_user.id)

        .order_by(Reservation.created_at.desc())

        .all()

    )

@router.get("/calendar", response_model=list[ReservationResponse])
def get_reservations_calendar(
    start_date: date = Query(...),
    end_date: date = Query(...),
    hotel_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if end_date < start_date:
        raise HTTPException(
            status_code=422,
            detail="End date must be on or after start date.",
        )

    query = (
        db.query(Reservation)
        .join(Room, Reservation.room_id == Room.id)
        .filter(
            Reservation.check_in <= end_date,
            Reservation.check_out > start_date,
        )
    )

    if current_user.role == UserRole.CUSTOMER:
        query = query.filter(Reservation.customer_id == current_user.id)
    elif current_user.role == UserRole.HOTEL_OWNER:
        query = query.join(Hotel, Room.hotel_id == Hotel.id).filter(
            Hotel.owner_id == current_user.id
        )
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied.")

    if hotel_id is not None:
        query = query.filter(Room.hotel_id == hotel_id)

    return query.order_by(Reservation.check_in.asc()).all()


@router.get("/schedule/check-ins", response_model=list[ReservationResponse])
def get_check_in_schedule(
    scheduled_date: date = Query(...),
    hotel_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        db.query(Reservation)
        .join(Room, Reservation.room_id == Room.id)
        .filter(
            Reservation.check_in == scheduled_date,
            Reservation.status == ReservationStatus.CONFIRMED,
        )
    )

    if current_user.role == UserRole.CUSTOMER:
        query = query.filter(Reservation.customer_id == current_user.id)
    elif current_user.role == UserRole.HOTEL_OWNER:
        query = query.join(Hotel, Room.hotel_id == Hotel.id).filter(
            Hotel.owner_id == current_user.id
        )
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied.")

    if hotel_id is not None:
        query = query.filter(Room.hotel_id == hotel_id)

    return query.order_by(Reservation.check_in.asc()).all()


@router.get("/schedule/check-outs", response_model=list[ReservationResponse])
def get_check_out_schedule(
    scheduled_date: date = Query(...),
    hotel_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        db.query(Reservation)
        .join(Room, Reservation.room_id == Room.id)
        .filter(
            Reservation.check_out == scheduled_date,
            Reservation.status == ReservationStatus.CONFIRMED,
        )
    )

    if current_user.role == UserRole.CUSTOMER:
        query = query.filter(Reservation.customer_id == current_user.id)
    elif current_user.role == UserRole.HOTEL_OWNER:
        query = query.join(Hotel, Room.hotel_id == Hotel.id).filter(
            Hotel.owner_id == current_user.id
        )
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied.")

    if hotel_id is not None:
        query = query.filter(Room.hotel_id == hotel_id)

    return query.order_by(Reservation.check_out.asc()).all()


@router.get("/availability")

def get_available_rooms(

    hotel_id: int = Query(gt=0),

    check_in: date = Query(),

    check_out: date = Query(),

    guests: int = Query(default=1, ge=1, le=100),

    db: Session = Depends(get_db),

    current_user: User = Depends(get_current_user),

):

    nights = validate_booking_dates(check_in, check_out)

    hotel = (

        db.query(Hotel)

        .filter(

            Hotel.id == hotel_id,

            Hotel.status == HotelStatus.APPROVED,

        )

        .first()

    )

    if hotel is None:

        raise HTTPException(

            status_code=404,

            detail="Approved hotel not found.",

        )

    rooms = (

        db.query(Room, RoomType)

        .join(

            RoomType,

            (RoomType.id == Room.room_type_id)

            & (RoomType.hotel_id == Room.hotel_id),

        )

        .filter(

            Room.hotel_id == hotel_id,

            Room.status == RoomStatus.AVAILABLE,

            Room.capacity >= guests,

            RoomType.capacity >= guests,

        )

        .all()

    )

    available_rooms = []

    for room, room_type in rooms:

        conflict = (

            db.query(Reservation.id)

            .filter(

                Reservation.room_id == room.id,

                Reservation.status == ReservationStatus.CONFIRMED,

                Reservation.check_in < check_out,

                Reservation.check_out > check_in,

            )

            .first()

        )

        if conflict:

            continue

        pricing = calculate_room_price(

            db=db,

            room_id=room.id,

            check_in=check_in,

            check_out=check_out,

        )

        available_rooms.append(

            {

                "id": room.id,

                "hotel_id": room.hotel_id,

                "room_type_id": room_type.id,

                "room_number": room.room_number,

                "capacity": min(room.capacity, room_type.capacity),

                "price_per_night": pricing["nightly_prices"][0],

                "total_price": pricing["total_price"],

                "status": room.status,

            }

        )

    return {

        "hotel_id": hotel_id,

        "check_in": check_in,

        "check_out": check_out,

        "nights": nights,

        "guests": guests,

        "available_rooms": available_rooms,

    }

@router.get(

    "/{reservation_id}",

    response_model=ReservationResponse,

)

def get_reservation(

    reservation_id: int,

    db: Session = Depends(get_db),

    current_user: User = Depends(get_current_user),

):

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

    if current_user.role == UserRole.CUSTOMER:

        if reservation.customer_id != current_user.id:

            raise HTTPException(

                status_code=403,

                detail="Access denied.",

            )

    elif current_user.role == UserRole.HOTEL_OWNER:

        room = (

            db.query(Room)

            .filter(Room.id == reservation.room_id)

            .first()

        )

        hotel = (

            db.query(Hotel).filter(Hotel.id == room.hotel_id).first()

            if room

            else None

        )

        if hotel is None or hotel.owner_id != current_user.id:

            raise HTTPException(

                status_code=403,

                detail="Access denied.",

            )

    elif current_user.role != UserRole.ADMIN:

        raise HTTPException(

            status_code=403,

            detail="Access denied.",

        )

    return reservation

@router.patch(

    "/{reservation_id}/modify",

    response_model=ReservationResponse,

)

def modify_reservation(

    reservation_id: int,

    payload: ReservationModify,

    db: Session = Depends(get_db),

    current_user: User = Depends(get_current_user),

):

    if current_user.role != UserRole.CUSTOMER:

        raise HTTPException(

            status_code=403,

            detail="Only customers can modify reservations.",

        )

    reservation = get_reservation_for_customer(

        reservation_id,

        db,

        current_user,

    )

    if reservation.status != ReservationStatus.CONFIRMED:

        raise HTTPException(

            status_code=409,

            detail="Only confirmed reservations can be modified.",

        )

    changes = payload.model_dump(exclude_unset=True)

    if not changes:

        raise HTTPException(

            status_code=422,

            detail="Provide at least one field to modify.",

        )

    new_room_id = changes.get("room_id", reservation.room_id)

    new_check_in = changes.get("check_in", reservation.check_in)

    new_check_out = changes.get("check_out", reservation.check_out)

    new_guest_count = changes.get(

        "guest_count",

        reservation.guest_count,

    )

    validate_booking_dates(new_check_in, new_check_out)

    room = db.query(Room).filter(Room.id == new_room_id).first()

    if room is None:

        raise HTTPException(

            status_code=404,

            detail="Room not found.",

        )

    if room.status != RoomStatus.AVAILABLE:

        raise HTTPException(

            status_code=409,

            detail="Room is not available for booking.",

        )

    conflict = (

        db.query(Reservation.id)

        .filter(

            Reservation.room_id == new_room_id,

            Reservation.id != reservation.id,

            Reservation.status == ReservationStatus.CONFIRMED,

            Reservation.check_in < new_check_out,

            Reservation.check_out > new_check_in,

        )

        .first()

    )

    if conflict:

        raise HTTPException(

            status_code=409,

            detail="Room is already booked for the selected dates.",

        )

    room_type = (

        db.query(RoomType)

        .filter(

            RoomType.id == room.room_type_id,

            RoomType.hotel_id == room.hotel_id,

        )

        .first()

    )

    if room_type is None:

        raise HTTPException(

            status_code=409,

            detail="The room does not have a valid room type.",

        )

    if new_guest_count > min(room.capacity, room_type.capacity):

        raise HTTPException(

            status_code=422,

            detail="Guest count exceeds the room capacity.",

        )

    hotel = db.query(Hotel).filter(Hotel.id == room.hotel_id).first()

    if hotel is None or hotel.status != HotelStatus.APPROVED:

        raise HTTPException(

            status_code=409,

            detail="Reservations are allowed only at approved hotels.",

        )

    pricing = calculate_room_price(

        db=db,

        room_id=room.id,

        check_in=new_check_in,

        check_out=new_check_out,

    )

    reservation.room_id = room.id

    reservation.check_in = new_check_in

    reservation.check_out = new_check_out

    reservation.guest_count = new_guest_count

    reservation.total_price = pricing["total_price"]

    try:

        record_audit_event(

            db=db,

            event_type=AuditEventType.BOOKING_UPDATED,

            action="BOOKING_UPDATED",

            actor_id=current_user.id,

            description="Customer modified a reservation.",

            entity_type="reservation",

            entity_id=reservation.id,

            details={

                "room_id": reservation.room_id,

                "check_in": reservation.check_in.isoformat(),

                "check_out": reservation.check_out.isoformat(),

                "guest_count": reservation.guest_count,

                "total_price": str(reservation.total_price),

            },

            commit=False,

        )

        db.commit()

        db.refresh(reservation)

    except IntegrityError:

        db.rollback()

        raise HTTPException(

            status_code=409,

            detail=(

                "Reservation could not be modified "

                "because of a conflicting record."

            ),

        )

    return reservation

@router.patch(

    "/{reservation_id}/cancel",

    response_model=ReservationCancelResponse,

)

def cancel_reservation(

    reservation_id: int,

    db: Session = Depends(get_db),

    current_user: User = Depends(get_current_user),

):

    if current_user.role != UserRole.CUSTOMER:

        raise HTTPException(

            status_code=403,

            detail="Only customers can cancel reservations.",

        )

    reservation = get_reservation_for_customer(

        reservation_id,

        db,

        current_user,

    )

    if reservation.status != ReservationStatus.CONFIRMED:

        raise HTTPException(

            status_code=409,

            detail="Only confirmed reservations can be cancelled.",

        )

    reservation.status = ReservationStatus.CANCELLED

    try:

        # Module 24: notify the customer about the cancellation.

        db.add(

            Notification(

                user_id=current_user.id,

                title="Reservation cancelled",

                message=(

                    f"Your reservation #{reservation.id} "

                    "has been cancelled."

                ),

                notification_type="reservation_cancelled",

                related_reservation_id=reservation.id,

                metadata_json={

                    "reservation_id": reservation.id,

                    "room_id": reservation.room_id,

                    "check_in": reservation.check_in.isoformat(),

                    "check_out": reservation.check_out.isoformat(),

                },

            )

        )

        record_audit_event(

            db=db,

            event_type=AuditEventType.BOOKING_CANCELLED,

            action="BOOKING_CANCELLED",

            actor_id=current_user.id,

            description="Customer cancelled a reservation.",

            entity_type="reservation",

            entity_id=reservation.id,

            details={"status": reservation.status.value},

            commit=False,

        )

        db.commit()

        db.refresh(reservation)

    except IntegrityError:

        db.rollback()

        raise HTTPException(

            status_code=409,

            detail="Reservation could not be cancelled.",

        )

    return ReservationCancelResponse(

        message="Reservation cancelled successfully.",

        reservation_id=reservation.id,

        status=reservation.status,

    )

@router.patch(
    "/{reservation_id}/status",
    response_model=ReservationResponse,
)
def update_reservation_status(
    reservation_id: int,
    payload: ReservationStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (UserRole.ADMIN, UserRole.CUSTOMER):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to update reservation status.",
        )

    query = db.query(Reservation).filter(
        Reservation.id == reservation_id
    )

    if current_user.role == UserRole.CUSTOMER:
        query = query.filter(
            Reservation.customer_id == current_user.id
        )

    reservation = query.first()

    if reservation is None:
        raise HTTPException(
            status_code=404,
            detail="Reservation not found.",
        )

    current_status = reservation.status
    new_status = payload.status

    allowed_transitions = {
        ReservationStatus.CONFIRMED: {
            ReservationStatus.CANCELLED,
            ReservationStatus.COMPLETED,
        },
        ReservationStatus.CANCELLED: set(),
        ReservationStatus.COMPLETED: set(),
    }

    if new_status == current_status:
        raise HTTPException(
            status_code=409,
            detail="Reservation already has this status.",
        )

    if new_status not in allowed_transitions[current_status]:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Invalid status transition: "
                f"{current_status.value} -> {new_status.value}."
            ),
        )

    if new_status == ReservationStatus.COMPLETED:
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=403,
                detail="Only administrators can complete reservations.",
            )

        if reservation.check_out > date.today():
            raise HTTPException(
                status_code=409,
                detail="A reservation cannot be completed before check-out.",
            )

        from sqlalchemy import select
        from app.models.payment import Payment, PaymentStatus

        successful_payment = db.scalar(
            select(Payment).where(
                Payment.reservation_id == reservation.id,
                Payment.customer_id == reservation.customer_id,
                Payment.status == PaymentStatus.SUCCEEDED,
            )
        )

        if successful_payment is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "A successful payment is required to complete "
                    "this reservation."
                ),
            )

    reservation.status = new_status

    try:
        if new_status == ReservationStatus.COMPLETED:
            award_booking_points(
                db=db,
                reservation=reservation,
                user_id=reservation.customer_id,
            )

        record_audit_event(
            db=db,
            event_type=(
                AuditEventType.ADMIN_ACTION
                if current_user.role == UserRole.ADMIN
                else AuditEventType.BOOKING_CANCELLED
            ),
            action="RESERVATION_STATUS_UPDATED",
            actor_id=current_user.id,
            description="Reservation status was updated.",
            entity_type="reservation",
            entity_id=reservation.id,
            details={
                "old_status": current_status.value,
                "new_status": new_status.value,
            },
            commit=False,
        )

        db.commit()
        db.refresh(reservation)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Reservation status could not be updated.",
        )

    except (ValueError, PermissionError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return reservation
