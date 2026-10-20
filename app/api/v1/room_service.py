
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import (
    Hotel,
    MenuItem,
    Reservation,
    ReservationStatus,
    Room,
    RoomServiceOrder,
    RoomServiceOrderHistory,
    RoomServiceOrderItem,
    RoomServiceOrderStatus,
    User,
    UserRole,
)
from app.schemas.room_service import (
    MenuItemCreate,
    MenuItemResponse,
    MenuItemUpdate,
    RoomServiceOrderCreate,
    RoomServiceOrderHistoryResponse,
    RoomServiceOrderResponse,
    RoomServiceOrderStatusUpdate,
)

router = APIRouter(
    prefix="/room-service",
    tags=["Room Service Management"],
)


# ---------------------------------------------------------
# AUTHORIZATION AND LOOKUP HELPERS
# ---------------------------------------------------------

def require_admin_or_hotel_owner(user: User) -> None:
    if user.role not in (UserRole.ADMIN, UserRole.HOTEL_OWNER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators or hotel owners can manage menu items.",
        )


def get_hotel_or_404(hotel_id: int, db: Session) -> Hotel:
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()

    if hotel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hotel not found.",
        )

    return hotel


def require_hotel_access(hotel: Hotel, user: User) -> None:
    if user.role == UserRole.ADMIN:
        return

    if user.role == UserRole.HOTEL_OWNER and hotel.owner_id == user.id:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You are not authorized to manage this hotel's room service.",
    )


def get_menu_item_or_404(
    menu_item_id: int,
    db: Session,
) -> MenuItem:
    menu_item = (
        db.query(MenuItem)
        .filter(MenuItem.id == menu_item_id)
        .first()
    )

    if menu_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found.",
        )

    return menu_item


def get_order_or_404(
    order_id: int,
    db: Session,
) -> RoomServiceOrder:
    order = (
        db.query(RoomServiceOrder)
        .filter(RoomServiceOrder.id == order_id)
        .first()
    )

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room service order not found.",
        )

    return order


def get_reservation_hotel(
    reservation: Reservation,
    db: Session,
) -> Hotel:
    room = (
        db.query(Room)
        .filter(Room.id == reservation.room_id)
        .first()
    )

    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation room not found.",
        )

    return get_hotel_or_404(room.hotel_id, db)


def authorize_order_access(
    order: RoomServiceOrder,
    user: User,
    db: Session,
) -> Reservation:
    reservation = (
        db.query(Reservation)
        .filter(Reservation.id == order.reservation_id)
        .first()
    )

    if reservation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found.",
        )

    hotel = get_hotel_or_404(order.hotel_id, db)

    if user.role == UserRole.ADMIN:
        return reservation

    if user.role == UserRole.CUSTOMER:
        if reservation.customer_id == user.id:
            return reservation

    elif user.role == UserRole.HOTEL_OWNER:
        if hotel.owner_id == user.id:
            return reservation

    elif user.role == UserRole.HOTEL_STAFF:
        # Staff may access orders for their hotel's operations.
        # A staff-to-hotel assignment check should be added if
        # the project has a defined staff-hotel assignment model.
        return reservation

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You are not authorized to access this order.",
    )


def record_order_history(
    order: RoomServiceOrder,
    user: User,
    notes: str,
    db: Session,
) -> None:
    db.add(
        RoomServiceOrderHistory(
            order_id=order.id,
            status=order.status,
            notes=notes,
            changed_by=user.id,
        )
    )


def build_order_response(
    order: RoomServiceOrder,
) -> RoomServiceOrderResponse:
    return RoomServiceOrderResponse.model_validate(
        order,
        from_attributes=True,
    )


# ---------------------------------------------------------
# FOOD MENU MANAGEMENT
# ---------------------------------------------------------

@router.post(
    "/menu",
    response_model=MenuItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_menu_item(
    payload: MenuItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin_or_hotel_owner(current_user)

    hotel = get_hotel_or_404(payload.hotel_id, db)
    require_hotel_access(hotel, current_user)

    menu_item = MenuItem(
        hotel_id=payload.hotel_id,
        name=payload.name.strip(),
        description=payload.description,
        category=payload.category.strip(),
        price=payload.price,
        is_available=payload.is_available,
    )

    try:
        db.add(menu_item)
        db.commit()
        db.refresh(menu_item)
    except Exception:
        db.rollback()
        raise

    return menu_item


@router.get(
    "/hotels/{hotel_id}/menu",
    response_model=list[MenuItemResponse],
)
def list_menu_items(
    hotel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    hotel = get_hotel_or_404(hotel_id, db)
    query = db.query(MenuItem).filter(MenuItem.hotel_id == hotel_id)

    if current_user.role == UserRole.ADMIN:
        pass
    elif current_user.role == UserRole.HOTEL_OWNER:
        require_hotel_access(hotel, current_user)
    else:
        query = query.filter(MenuItem.is_available.is_(True))

    return query.order_by(MenuItem.category, MenuItem.name).all()


@router.patch(
    "/menu/{menu_item_id}",
    response_model=MenuItemResponse,
)
def update_menu_item(
    menu_item_id: int,
    payload: MenuItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin_or_hotel_owner(current_user)

    menu_item = get_menu_item_or_404(menu_item_id, db)
    hotel = get_hotel_or_404(menu_item.hotel_id, db)
    require_hotel_access(hotel, current_user)

    changes = payload.model_dump(exclude_unset=True)

    if "name" in changes and changes["name"] is not None:
        changes["name"] = changes["name"].strip()

    if "category" in changes and changes["category"] is not None:
        changes["category"] = changes["category"].strip()

    for field, value in changes.items():
        setattr(menu_item, field, value)

    try:
        db.commit()
        db.refresh(menu_item)
    except Exception:
        db.rollback()
        raise

    return menu_item


# ---------------------------------------------------------
# CREATE ROOM SERVICE ORDERS
# ---------------------------------------------------------

@router.post(
    "/orders",
    response_model=RoomServiceOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_room_service_order(
    payload: RoomServiceOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (UserRole.CUSTOMER, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers or administrators can create orders.",
        )

    reservation = (
        db.query(Reservation)
        .filter(Reservation.id == payload.reservation_id)
        .first()
    )

    if reservation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found.",
        )

    if (
        current_user.role == UserRole.CUSTOMER
        and reservation.customer_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot order room service for another customer's reservation.",
        )

    if reservation.status != ReservationStatus.CONFIRMED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Room service is only available for confirmed reservations.",
        )

    hotel = get_reservation_hotel(reservation, db)

    subtotal = Decimal("0.00")
    order_items_data = []

    for requested_item in payload.items:
        menu_item = get_menu_item_or_404(requested_item.menu_item_id, db)

        if menu_item.hotel_id != hotel.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="All menu items must belong to the reservation's hotel.",
            )

        if not menu_item.is_available:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Menu item '{menu_item.name}' is unavailable.",
            )

        unit_price = Decimal(str(menu_item.price))
        line_total = (
            unit_price * requested_item.quantity
        ).quantize(Decimal("0.01"))

        subtotal += line_total

        order_items_data.append(
            {
                "menu_item_id": menu_item.id,
                "item_name": menu_item.name,
                "quantity": requested_item.quantity,
                "unit_price": unit_price,
                "line_total": line_total,
            }
        )

    subtotal = subtotal.quantize(Decimal("0.01"))
    service_charge = Decimal(str(payload.service_charge)).quantize(
        Decimal("0.01")
    )
    total_amount = (subtotal + service_charge).quantize(Decimal("0.01"))

    order = RoomServiceOrder(
        reservation_id=reservation.id,
        hotel_id=hotel.id,
        ordered_by=current_user.id,
        subtotal=subtotal,
        service_charge=service_charge,
        total_amount=total_amount,
        status=RoomServiceOrderStatus.ORDERED,
        special_instructions=payload.special_instructions,
    )

    try:
        db.add(order)
        db.flush()

        for item_data in order_items_data:
            db.add(
                RoomServiceOrderItem(
                    order_id=order.id,
                    **item_data,
                )
            )

        record_order_history(
            order,
            current_user,
            "Room service order created.",
            db,
        )

        db.commit()
        db.refresh(order)
    except Exception:
        db.rollback()
        raise

    return build_order_response(order)


# ---------------------------------------------------------
# LIST AND VIEW ORDERS
# ---------------------------------------------------------

@router.get(
    "/orders/my",
    response_model=list[RoomServiceOrderResponse],
)
def list_my_room_service_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(RoomServiceOrder)

    if current_user.role == UserRole.CUSTOMER:
        query = query.join(
            Reservation,
            RoomServiceOrder.reservation_id == Reservation.id,
        ).filter(Reservation.customer_id == current_user.id)

    elif current_user.role == UserRole.ADMIN:
        pass

    elif current_user.role == UserRole.HOTEL_OWNER:
        query = query.join(
            Hotel,
            RoomServiceOrder.hotel_id == Hotel.id,
        ).filter(Hotel.owner_id == current_user.id)

    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )

    orders = query.order_by(RoomServiceOrder.ordered_at.desc()).all()

    return [build_order_response(order) for order in orders]


@router.get(
    "/orders/{order_id}",
    response_model=RoomServiceOrderResponse,
)
def get_room_service_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = get_order_or_404(order_id, db)
    authorize_order_access(order, current_user, db)
    return build_order_response(order)


# ---------------------------------------------------------
# PREPARATION AND DELIVERY STATUS
# ---------------------------------------------------------

@router.patch(
    "/orders/{order_id}/status",
    response_model=RoomServiceOrderResponse,
)
def update_room_service_order_status(
    order_id: int,
    payload: RoomServiceOrderStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = get_order_or_404(order_id, db)
    authorize_order_access(order, current_user, db)

    if current_user.role not in (
        UserRole.ADMIN,
        UserRole.HOTEL_OWNER,
        UserRole.HOTEL_STAFF,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only hotel staff, hotel owners, or administrators can update order status.",
        )

    new_status = payload.status
    current_status = order.status

    allowed_transitions = {
        RoomServiceOrderStatus.ORDERED: {
            RoomServiceOrderStatus.PREPARING,
            RoomServiceOrderStatus.CANCELLED,
        },
        RoomServiceOrderStatus.PREPARING: {
            RoomServiceOrderStatus.READY,
            RoomServiceOrderStatus.CANCELLED,
        },
        RoomServiceOrderStatus.READY: {
            RoomServiceOrderStatus.OUT_FOR_DELIVERY,
            RoomServiceOrderStatus.DELIVERED,
            RoomServiceOrderStatus.CANCELLED,
        },
        RoomServiceOrderStatus.OUT_FOR_DELIVERY: {
            RoomServiceOrderStatus.DELIVERED,
        },
        RoomServiceOrderStatus.DELIVERED: set(),
        RoomServiceOrderStatus.CANCELLED: set(),
    }

    if new_status == current_status:
        return build_order_response(order)

    if new_status not in allowed_transitions[current_status]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot change order status from "
                f"{current_status.value} to {new_status.value}."
            ),
        )

    order.status = new_status

    if new_status == RoomServiceOrderStatus.DELIVERED:
        order.delivered_at = datetime.now(timezone.utc)

    try:
        record_order_history(
            order,
            current_user,
            f"Order status changed from {current_status.value} to {new_status.value}.",
            db,
        )
        db.commit()
        db.refresh(order)
    except Exception:
        db.rollback()
        raise

    return build_order_response(order)


# ---------------------------------------------------------
# ORDER HISTORY
# ---------------------------------------------------------

@router.get(
    "/orders/{order_id}/history",
    response_model=list[RoomServiceOrderHistoryResponse],
)
def get_room_service_order_history(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = get_order_or_404(order_id, db)
    authorize_order_access(order, current_user, db)

    return (
        db.query(RoomServiceOrderHistory)
        .filter(RoomServiceOrderHistory.order_id == order.id)
        .order_by(RoomServiceOrderHistory.changed_at.asc())
        .all()
    )
