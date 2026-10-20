
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.db.session import get_db
from app.models import User, UserRole
from app.models.coupon import Coupon, CouponType
from app.models.coupon_usage import CouponUsage
from app.schemas.coupon import (
    CouponApplyRequest,
    CouponApplyResponse,
    CouponCreate,
    CouponResponse,
)

router = APIRouter(prefix="/coupons", tags=["Coupons"])

require_admin = require_roles(UserRole.ADMIN)
require_customer = require_roles(UserRole.CUSTOMER)


@router.post(
    "",
    response_model=CouponResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_coupon(
    request: CouponCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    code = request.code.strip().upper()

    existing_coupon = (
        db.query(Coupon)
        .filter(Coupon.code == code)
        .first()
    )

    if existing_coupon:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A coupon with this code already exists.",
        )

    coupon_data = request.model_dump()
    coupon_data["code"] = code

    coupon = Coupon(**coupon_data)
    db.add(coupon)

    try:
        db.commit()
        db.refresh(coupon)
    except Exception:
        db.rollback()
        raise

    return coupon


@router.get("", response_model=list[CouponResponse])
def list_coupons(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.query(Coupon).order_by(Coupon.id.desc()).all()


@router.post("/apply", response_model=CouponApplyResponse)
def apply_coupon(
    request: CouponApplyRequest,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    code = request.code.strip().upper()

    coupon = (
        db.query(Coupon)
        .filter(Coupon.code == code)
        .first()
    )

    if coupon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Coupon not found.",
        )

    if not coupon.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Coupon is inactive.",
        )

    valid_from = coupon.valid_from
    expires_at = coupon.expires_at

    # MySQL may return naive datetimes even when timezone=True.
    if valid_from.tzinfo is None:
        valid_from = valid_from.replace(tzinfo=timezone.utc)

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now < valid_from or now > expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Coupon is not currently valid.",
        )

    if (
        coupon.usage_limit is not None
        and coupon.used_count >= coupon.usage_limit
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Coupon usage limit has been reached.",
        )

    if request.booking_amount < coupon.min_booking_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Minimum booking amount is "
                f"{coupon.min_booking_amount}."
            ),
        )

    existing_usage = (
        db.query(CouponUsage)
        .filter(
            CouponUsage.coupon_id == coupon.id,
            CouponUsage.user_id == current_user.id,
        )
        .first()
    )

    if existing_usage:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already used this coupon.",
        )

    check_in = request.check_in.date()
    days_until_checkin = (check_in - date.today()).days

    # Current default: early-booking coupons require 7 days' notice.
    if coupon.is_early_booking and days_until_checkin < 7:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This coupon requires booking at least "
                "7 days in advance."
            ),
        )

    # Current default: seasonal coupons apply to June through August.
    if coupon.is_seasonal and not (6 <= check_in.month <= 8):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This seasonal coupon is valid only "
                "for June through August."
            ),
        )

    booking_amount = request.booking_amount

    if coupon.coupon_type == CouponType.PERCENTAGE:
        discount = (
            booking_amount
            * coupon.discount_value
            / Decimal("100")
        )
    else:
        discount = coupon.discount_value

    # Never discount more than the booking amount.
    discount = min(discount, booking_amount)

    discount = discount.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    final_amount = (booking_amount - discount).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    return CouponApplyResponse(
        code=coupon.code,
        coupon_type=coupon.coupon_type,
        discount_value=coupon.discount_value,
        discount_amount=discount,
        final_amount=final_amount,
    )
