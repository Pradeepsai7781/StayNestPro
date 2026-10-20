
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import (
    AdditionalService,
    AdditionalServiceCategory,
    Hotel,
    Reservation,
    ReservationStatus,
    ReservationStay,
    Room,
    ServiceRequest,
    ServiceRequestHistory,
    ServiceRequestStatus,
    User,
    UserRole,
)
from app.schemas.additional_service import (
    AdditionalServiceCreate,
    AdditionalServiceResponse,
    AdditionalServiceUpdate,
    ServiceRequestCreate,
    ServiceRequestHistoryResponse,
    ServiceRequestResponse,
    ServiceRequestUpdate,
)

router = APIRouter(
    prefix="/additional-services",
    tags=["Additional Services Management"],
)


# ---------------------------------------------------------
# AUTHORIZATION AND DATABASE HELPERS
# ---------------------------------------------------------

def require_admin(user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can manage service pricing.",
        )


def get_reservation_or_404(
    reservation_id: int,
    db: Session,
) -> Reservation:
    reservation = (
        db.query(Reservation)
        .filter(Reservation.id == reservation_id)
        .first()
    )

    if reservation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found.",
        )

    return reservation


def user_can_access_reservation(
    reservation: Reservation,
    user: User,
    db: Session,
) -> bool:
    if user.role == UserRole.ADMIN:
        return True

    if user.role == UserRole.CUSTOMER:
        return reservation.customer_id == user.id

    if user.role == UserRole.HOTEL_OWNER:
        room = (
            db.query(Room)
            .filter(Room.id == reservation.room_id)
            .first()
        )

        if room is None:
            return False

        hotel = (
            db.query(Hotel)
            .filter(Hotel.id == room.hotel_id)
            .first()
        )

        return hotel is not None and hotel.owner_id == user.id

    return False


def get_service_or_404(
    service_id: int,
    db: Session,
) -> AdditionalService:
    service = (
        db.query(AdditionalService)
        .filter(AdditionalService.id == service_id)
        .first()
    )

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Additional service not found.",
        )

    return service


def get_request_or_404(
    request_id: int,
    db: Session,
) -> ServiceRequest:
    service_request = (
        db.query(ServiceRequest)
        .filter(ServiceRequest.id == request_id)
        .first()
    )

    if service_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service request not found.",
        )

    return service_request


def authorize_service_request(
    service_request: ServiceRequest,
    user: User,
    db: Session,
) -> Reservation:
    reservation = get_reservation_or_404(
        service_request.reservation_id,
        db,
    )

    if not user_can_access_reservation(reservation, user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this service request.",
        )

    return reservation


def record_service_history(
    service_request: ServiceRequest,
    notes: str,
    db: Session,
) -> None:
    db.add(
        ServiceRequestHistory(
            service_request_id=service_request.id,
            status=service_request.status,
            notes=notes,
        )
    )


# ---------------------------------------------------------
# SERVICE CATALOG AND PRICING
# ---------------------------------------------------------

@router.post(
    "",
    response_model=AdditionalServiceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_additional_service(
    payload: AdditionalServiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    service = AdditionalService(
        name=payload.name.strip(),
        category=payload.category,
        description=payload.description,
        price=payload.price,
        is_available=payload.is_available,
    )

    db.add(service)

    try:
        db.commit()
        db.refresh(service)
    except Exception:
        db.rollback()
        raise

    return service


@router.get(
    "",
    response_model=list[AdditionalServiceResponse],
)
def list_additional_services(
    category: AdditionalServiceCategory | None = Query(default=None),
    include_unavailable: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(AdditionalService)

    if category is not None:
        query = query.filter(
            AdditionalService.category == category
        )

    if not (
        current_user.role == UserRole.ADMIN
        and include_unavailable
    ):
        query = query.filter(
            AdditionalService.is_available.is_(True)
        )

    return query.order_by(
        AdditionalService.category,
        AdditionalService.name,
    ).all()


@router.get(
    "/{service_id}",
    response_model=AdditionalServiceResponse,
)
def get_additional_service(
    service_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_service_or_404(service_id, db)

    if (
        not service.is_available
        and current_user.role != UserRole.ADMIN
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Additional service not found.",
        )

    return service


@router.patch(
    "/{service_id}",
    response_model=AdditionalServiceResponse,
)
def update_additional_service(
    service_id: int,
    payload: AdditionalServiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    service = get_service_or_404(service_id, db)
    changes = payload.model_dump(exclude_unset=True)

    if "name" in changes and changes["name"] is not None:
        changes["name"] = changes["name"].strip()

    for field, value in changes.items():
        setattr(service, field, value)

    try:
        db.commit()
        db.refresh(service)
    except Exception:
        db.rollback()
        raise

    return service


# ---------------------------------------------------------
# CREATE AND TRACK SERVICE REQUESTS
# ---------------------------------------------------------

@router.post(
    "/requests",
    response_model=ServiceRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_service_request(
    payload: ServiceRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (
        UserRole.CUSTOMER,
        UserRole.ADMIN,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers or administrators can create service requests.",
        )

    reservation = get_reservation_or_404(
        payload.reservation_id,
        db,
    )

    if not user_can_access_reservation(
        reservation,
        current_user,
        db,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot request services for this reservation.",
        )

    if reservation.status != ReservationStatus.CONFIRMED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Services can only be requested for confirmed reservations.",
        )

    stay = (
        db.query(ReservationStay)
        .filter(
            ReservationStay.reservation_id == reservation.id
        )
        .first()
    )

    if stay is not None and stay.actual_check_out is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Services cannot be requested after check-out.",
        )

    service = get_service_or_404(
        payload.service_id,
        db,
    )

    if not service.is_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This service is currently unavailable.",
        )

    unit_price = Decimal(str(service.price))
    total_charge = (
        unit_price * payload.quantity
    ).quantize(Decimal("0.01"))

    service_request = ServiceRequest(
        reservation_id=reservation.id,
        service_id=service.id,
        requested_by=current_user.id,
        quantity=payload.quantity,
        unit_price=unit_price,
        total_charge=total_charge,
        status=ServiceRequestStatus.REQUESTED,
        special_instructions=payload.special_instructions,
    )

    try:
        db.add(service_request)
        db.flush()

        record_service_history(
            service_request,
            "Service request created.",
            db,
        )

        db.commit()
        db.refresh(service_request)
    except Exception:
        db.rollback()
        raise

    return service_request


@router.get(
    "/requests/my",
    response_model=list[ServiceRequestResponse],
)
def list_my_service_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(ServiceRequest)

    if current_user.role == UserRole.CUSTOMER:
        query = query.filter(
            ServiceRequest.requested_by == current_user.id
        )

    elif current_user.role == UserRole.ADMIN:
        pass

    elif current_user.role == UserRole.HOTEL_OWNER:
        reservation_ids = (
            db.query(Reservation.id)
            .join(Room, Reservation.room_id == Room.id)
            .join(Hotel, Room.hotel_id == Hotel.id)
            .filter(Hotel.owner_id == current_user.id)
        )

        query = query.filter(
            ServiceRequest.reservation_id.in_(reservation_ids)
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )

    return query.order_by(
        ServiceRequest.requested_at.desc()
    ).all()


@router.get(
    "/requests/{request_id}",
    response_model=ServiceRequestResponse,
)
def get_service_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service_request = get_request_or_404(
        request_id,
        db,
    )

    authorize_service_request(
        service_request,
        current_user,
        db,
    )

    return service_request


@router.patch(
    "/requests/{request_id}/status",
    response_model=ServiceRequestResponse,
)
def update_service_request_status(
    request_id: int,
    payload: ServiceRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service_request = get_request_or_404(
        request_id,
        db,
    )

    reservation = authorize_service_request(
        service_request,
        current_user,
        db,
    )

    if current_user.role not in (
        UserRole.ADMIN,
        UserRole.HOTEL_OWNER,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators or hotel owners can update request status.",
        )

    if current_user.role == UserRole.HOTEL_OWNER:
        room = (
            db.query(Room)
            .filter(Room.id == reservation.room_id)
            .first()
        )

        hotel = (
            db.query(Hotel)
            .filter(Hotel.id == room.hotel_id)
            .first()
            if room is not None
            else None
        )

        if hotel is None or hotel.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied.",
            )

    current_status = service_request.status
    new_status = payload.status

    allowed_transitions = {
        ServiceRequestStatus.REQUESTED: {
            ServiceRequestStatus.CONFIRMED,
            ServiceRequestStatus.CANCELLED,
        },
        ServiceRequestStatus.CONFIRMED: {
            ServiceRequestStatus.IN_PROGRESS,
            ServiceRequestStatus.CANCELLED,
        },
        ServiceRequestStatus.IN_PROGRESS: {
            ServiceRequestStatus.COMPLETED,
            ServiceRequestStatus.CANCELLED,
        },
        ServiceRequestStatus.COMPLETED: set(),
        ServiceRequestStatus.CANCELLED: set(),
    }

    if new_status == current_status:
        return service_request

    if new_status not in allowed_transitions[current_status]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot change service request from "
                f"{current_status.value} to {new_status.value}."
            ),
        )

    service_request.status = new_status

    if new_status == ServiceRequestStatus.COMPLETED:
        service_request.completed_at = datetime.now(timezone.utc)

    try:
        record_service_history(
            service_request,
            f"Status changed from {current_status.value} to {new_status.value}.",
            db,
        )

        db.commit()
        db.refresh(service_request)
    except Exception:
        db.rollback()
        raise

    return service_request


# ---------------------------------------------------------
# SERVICE HISTORY
# ---------------------------------------------------------

@router.get(
    "/reservations/{reservation_id}/history",
)
def get_reservation_service_history(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reservation = get_reservation_or_404(
        reservation_id,
        db,
    )

    if not user_can_access_reservation(
        reservation,
        current_user,
        db,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access this reservation's service history.",
        )

    history_entries = (
        db.query(ServiceRequestHistory)
        .join(
            ServiceRequest,
            ServiceRequestHistory.service_request_id == ServiceRequest.id,
        )
        .filter(
            ServiceRequest.reservation_id == reservation.id
        )
        .order_by(ServiceRequestHistory.changed_at.asc())
        .all()
    )

    return [
        {
            "id": entry.id,
            "service_request_id": entry.service_request_id,
            "status": entry.status,
            "notes": entry.notes,
            "changed_at": entry.changed_at,
        }
        for entry in history_entries
    ]


@router.get(
    "/requests/{request_id}/history",
)
def get_service_request_history(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service_request = get_request_or_404(
        request_id,
        db,
    )

    authorize_service_request(
        service_request,
        current_user,
        db,
    )

    history_entries = (
        db.query(ServiceRequestHistory)
        .filter(
            ServiceRequestHistory.service_request_id
            == service_request.id
        )
        .order_by(ServiceRequestHistory.changed_at.asc())
        .all()
    )

    return [
        {
            "id": entry.id,
            "service_request_id": entry.service_request_id,
            "status": entry.status,
            "notes": entry.notes,
            "changed_at": entry.changed_at,
        }
        for entry in history_entries
    ]
