
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import Hotel, Room, User, UserRole
from app.models.dynamic_pricing import (
    DynamicPricing,
    PricingAdjustmentType,
    PricingRuleType,
)
from app.schemas.dynamic_pricing import (
    DynamicPricingCreate,
    DynamicPricingResponse,
    DynamicPricingUpdate,
    RoomPriceResponse,
)
from app.services.dynamic_pricing_service import (
    calculate_room_price,
    validate_rule_conflicts,
)


router = APIRouter(
    prefix="/dynamic-pricing",
    tags=["Dynamic Pricing"],
)


def verify_room_access(
    db: Session,
    room_id: int,
    current_user: User,
) -> Room:
    room = db.query(Room).filter(Room.id == room_id).first()

    if room is None:
        raise HTTPException(
            status_code=404,
            detail="Room not found.",
        )

    hotel = db.query(Hotel).filter(Hotel.id == room.hotel_id).first()

    if hotel is None:
        raise HTTPException(
            status_code=404,
            detail="Hotel not found.",
        )

    if current_user.role == UserRole.ADMIN:
        return room

    if (
        current_user.role == UserRole.HOTEL_OWNER
        and hotel.owner_id == current_user.id
    ):
        return room

    raise HTTPException(
        status_code=403,
        detail="You do not have permission to manage this room's pricing.",
    )


@router.post(
    "/rules",
    response_model=DynamicPricingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_pricing_rule(
    payload: DynamicPricingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    verify_room_access(db, payload.room_id, current_user)

    validate_rule_conflicts(
        db=db,
        room_id=payload.room_id,
        rule_type=payload.rule_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )

    rule = DynamicPricing(**payload.model_dump())

    db.add(rule)
    db.commit()
    db.refresh(rule)

    return rule


@router.get(
    "/rules",
    response_model=list[DynamicPricingResponse],
)
def list_pricing_rules(
    room_id: int = Query(gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    verify_room_access(db, room_id, current_user)

    return (
        db.query(DynamicPricing)
        .filter(DynamicPricing.room_id == room_id)
        .order_by(
            DynamicPricing.start_date.asc(),
            DynamicPricing.priority.desc(),
        )
        .all()
    )


@router.patch(
    "/rules/{rule_id}",
    response_model=DynamicPricingResponse,
)
def update_pricing_rule(
    rule_id: int,
    payload: DynamicPricingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = (
        db.query(DynamicPricing)
        .filter(DynamicPricing.id == rule_id)
        .first()
    )

    if rule is None:
        raise HTTPException(
            status_code=404,
            detail="Pricing rule not found.",
        )

    verify_room_access(db, rule.room_id, current_user)

    changes = payload.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=422,
            detail="Provide at least one field to update.",
        )

    new_start_date = changes.get("start_date", rule.start_date)
    new_end_date = changes.get("end_date", rule.end_date)
    new_rule_type = changes.get("rule_type", rule.rule_type)
    new_adjustment_type = changes.get(
        "adjustment_type",
        rule.adjustment_type,
    )
    new_adjustment_value = changes.get(
        "adjustment_value",
        rule.adjustment_value,
    )

    if new_end_date < new_start_date:
        raise HTTPException(
            status_code=422,
            detail="End date must be on or after start date.",
        )

    if (
        new_rule_type == PricingRuleType.PROMOTIONAL
        and new_adjustment_type == PricingAdjustmentType.PERCENTAGE
        and Decimal(str(new_adjustment_value)) > Decimal("100")
    ):
        raise HTTPException(
            status_code=422,
            detail="Promotional percentage cannot exceed 100.",
        )

    validate_rule_conflicts(
        db=db,
        room_id=rule.room_id,
        rule_type=new_rule_type,
        start_date=new_start_date,
        end_date=new_end_date,
        exclude_rule_id=rule.id,
    )

    for field, value in changes.items():
        setattr(rule, field, value)

    db.commit()
    db.refresh(rule)

    return rule


@router.delete(
    "/rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_pricing_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = (
        db.query(DynamicPricing)
        .filter(DynamicPricing.id == rule_id)
        .first()
    )

    if rule is None:
        raise HTTPException(
            status_code=404,
            detail="Pricing rule not found.",
        )

    verify_room_access(db, rule.room_id, current_user)

    db.delete(rule)
    db.commit()


@router.get(
    "/rooms/{room_id}/calculate",
    response_model=RoomPriceResponse,
)
def get_calculated_room_price(
    room_id: int,
    check_in: date = Query(),
    check_out: date = Query(),
    db: Session = Depends(get_db),
):
    return calculate_room_price(
        db=db,
        room_id=room_id,
        check_in=check_in,
        check_out=check_out,
    )
