
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.dynamic_pricing import (
    DynamicPricing,
    PricingAdjustmentType,
    PricingRuleType,
)
from app.models.room import Room
from app.models.room_type import RoomType


def money(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def validate_rule_conflicts(
    db: Session,
    room_id: int,
    rule_type: PricingRuleType,
    start_date: date,
    end_date: date,
    exclude_rule_id: int | None = None,
) -> None:
    query = db.query(DynamicPricing).filter(
        DynamicPricing.room_id == room_id,
        DynamicPricing.rule_type == rule_type,
        DynamicPricing.start_date <= end_date,
        DynamicPricing.end_date >= start_date,
    )

    if exclude_rule_id is not None:
        query = query.filter(
            DynamicPricing.id != exclude_rule_id
        )

    if query.first():
        raise HTTPException(
            status_code=409,
            detail=(
                "A pricing rule of this type already overlaps "
                "the selected dates for this room."
            ),
        )


def get_room_base_price(
    db: Session,
    room_id: int,
) -> Decimal:
    room = db.query(Room).filter(Room.id == room_id).first()

    if room is None:
        raise HTTPException(
            status_code=404,
            detail="Room not found.",
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

    return Decimal(str(room_type.price_per_night))


def calculate_nightly_price(
    base_price: Decimal,
    rules: list[DynamicPricing],
) -> tuple[Decimal, list[str]]:
    fixed_rules = [
        rule
        for rule in rules
        if rule.adjustment_type == PricingAdjustmentType.FIXED_PRICE
    ]

    applied_rules: list[str] = []
    price = base_price

    if fixed_rules:
        selected_rule = sorted(
            fixed_rules,
            key=lambda rule: (rule.priority, rule.id),
            reverse=True,
        )[0]

        price = Decimal(str(selected_rule.adjustment_value))
        applied_rules.append(selected_rule.name)

    else:
        percentage_rules = sorted(
            [
                rule
                for rule in rules
                if rule.adjustment_type
                == PricingAdjustmentType.PERCENTAGE
            ],
            key=lambda rule: (rule.priority, rule.id),
        )

        for rule in percentage_rules:
            percentage = Decimal(str(rule.adjustment_value))
            adjustment = price * percentage / Decimal("100")

            if rule.rule_type == PricingRuleType.PROMOTIONAL:
                price -= adjustment
            else:
                price += adjustment

            applied_rules.append(rule.name)

    return max(money(price), Decimal("0.00")), applied_rules


def calculate_room_price(
    db: Session,
    room_id: int,
    check_in: date,
    check_out: date,
) -> dict:
    if check_out <= check_in:
        raise HTTPException(
            status_code=422,
            detail="Check-out must be after check-in.",
        )

    base_price = get_room_base_price(db, room_id)

    rules = (
        db.query(DynamicPricing)
        .filter(
            DynamicPricing.room_id == room_id,
            DynamicPricing.start_date < check_out,
            DynamicPricing.end_date >= check_in,
        )
        .order_by(
            DynamicPricing.priority.asc(),
            DynamicPricing.id.asc(),
        )
        .all()
    )

    nightly_prices: list[Decimal] = []
    applied_rules: list[str] = []
    current_date = check_in

    while current_date < check_out:
        matching_rules = []

        for rule in rules:
            if not (
                rule.start_date <= current_date <= rule.end_date
            ):
                continue

            if (
                rule.rule_type == PricingRuleType.WEEKEND
                and current_date.weekday() < 5
            ):
                continue

            matching_rules.append(rule)

        nightly_price, nightly_rule_names = calculate_nightly_price(
            base_price,
            matching_rules,
        )

        nightly_prices.append(nightly_price)

        for rule_name in nightly_rule_names:
            if rule_name not in applied_rules:
                applied_rules.append(rule_name)

        current_date += timedelta(days=1)

    total_price = money(sum(nightly_prices, Decimal("0.00")))

    return {
        "room_id": room_id,
        "check_in": check_in,
        "check_out": check_out,
        "number_of_nights": len(nightly_prices),
        "nightly_prices": nightly_prices,
        "total_price": total_price,
        "applied_rules": applied_rules,
    }
