
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import Hotel, Reservation, Room, User, UserRole
from app.models.guest import Guest
from app.schemas.guest import GuestCreate, GuestResponse, GuestUpdate


router = APIRouter(prefix="/guests", tags=["Guests"])


def get_reservation_or_404(
    db: Session,
    reservation_id: int,
) -> Reservation:
    reservation = (
        db.query(Reservation)
        .filter(Reservation.id == reservation_id)
        .first()
    )

    if reservation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found",
        )

    return reservation


def can_access_reservation(
    db: Session,
    reservation: Reservation,
    user: User,
) -> bool:
    if user.role == UserRole.ADMIN:
        return True

    if (
        user.role == UserRole.CUSTOMER
        and reservation.customer_id == user.id
    ):
        return True

    if user.role == UserRole.HOTEL_OWNER:
        owns_hotel = (
            db.query(Hotel)
            .join(Room, Room.hotel_id == Hotel.id)
            .filter(
                Room.id == reservation.room_id,
                Hotel.owner_id == user.id,
            )
            .first()
        )
        return owns_hotel is not None

    return False


def require_reservation_access(
    db: Session,
    reservation: Reservation,
    user: User,
) -> None:
    if not can_access_reservation(db, reservation, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this reservation",
        )


def get_guest_or_404(db: Session, guest_id: int) -> Guest:
    guest = db.query(Guest).filter(Guest.id == guest_id).first()

    if guest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest not found",
        )

    return guest


@router.post(
    "/reservations/{reservation_id}",
    response_model=GuestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_guest(
    reservation_id: int,
    guest_data: GuestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reservation = get_reservation_or_404(db, reservation_id)
    require_reservation_access(db, reservation, current_user)

    if current_user.role == UserRole.HOTEL_OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hotel owners cannot add guests to customer reservations",
        )

    guest_count = (
        db.query(Guest)
        .filter(Guest.reservation_id == reservation_id)
        .count()
    )

    if guest_count >= reservation.guest_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Guest limit reached for this reservation",
        )

    guest = Guest(
        reservation_id=reservation_id,
        **guest_data.model_dump(),
    )

    db.add(guest)
    db.commit()
    db.refresh(guest)

    return guest


@router.get(
    "/reservations/{reservation_id}",
    response_model=list[GuestResponse],
)
def list_reservation_guests(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reservation = get_reservation_or_404(db, reservation_id)
    require_reservation_access(db, reservation, current_user)

    return (
        db.query(Guest)
        .filter(Guest.reservation_id == reservation_id)
        .order_by(Guest.id.asc())
        .all()
    )


@router.patch("/{guest_id}", response_model=GuestResponse)
def update_guest(
    guest_id: int,
    guest_data: GuestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    guest = get_guest_or_404(db, guest_id)
    reservation = get_reservation_or_404(db, guest.reservation_id)

    require_reservation_access(db, reservation, current_user)

    if current_user.role == UserRole.HOTEL_OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hotel owners cannot modify customer guest records",
        )

    updates = guest_data.model_dump(exclude_unset=True)

    # Validate the complete ID pair, including existing values.
    resulting_id_type = updates.get("id_type", guest.id_type)
    resulting_id_number = updates.get(
        "id_number_masked",
        guest.id_number_masked,
    )

    if bool(resulting_id_type) != bool(resulting_id_number):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Identification type and masked ID reference "
                "must be provided together"
            ),
        )

    for field, value in updates.items():
        setattr(guest, field, value)

    db.commit()
    db.refresh(guest)

    return guest


@router.delete("/{guest_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_guest(
    guest_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    guest = get_guest_or_404(db, guest_id)
    reservation = get_reservation_or_404(db, guest.reservation_id)

    require_reservation_access(db, reservation, current_user)

    if current_user.role == UserRole.HOTEL_OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hotel owners cannot delete customer guest records",
        )

    db.delete(guest)
    db.commit()

    return None


@router.get("/history", response_model=list[GuestResponse])
def get_guest_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        db.query(Guest)
        .join(Reservation, Guest.reservation_id == Reservation.id)
    )

    if current_user.role == UserRole.CUSTOMER:
        query = query.filter(Reservation.customer_id == current_user.id)

    elif current_user.role == UserRole.HOTEL_OWNER:
        query = (
            query.join(Room, Reservation.room_id == Room.id)
            .join(Hotel, Room.hotel_id == Hotel.id)
            .filter(Hotel.owner_id == current_user.id)
        )

    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view guest history",
        )

    return query.order_by(Guest.created_at.desc()).all()
