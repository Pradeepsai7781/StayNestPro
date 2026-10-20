
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import (
    Amenity,
    Hotel,
    User,
    UserRole,
    hotel_amenities,
)
from app.schemas.amenity import (
    AmenityCreate,
    AmenityResponse,
    AmenityUpdate,
)


router = APIRouter(prefix="/amenities", tags=["Amenities"])


def require_admin(user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can manage the amenity catalog",
        )


def get_owned_hotel(
    hotel_id: int,
    current_user: User,
    db: Session,
) -> Hotel:
    if current_user.role != UserRole.HOTEL_OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only hotel owners can manage their hotel amenities",
        )

    hotel = (
        db.query(Hotel)
        .filter(
            Hotel.id == hotel_id,
            Hotel.owner_id == current_user.id,
        )
        .first()
    )

    if hotel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hotel not found",
        )

    return hotel


def get_amenity(amenity_id: int, db: Session) -> Amenity:
    amenity = (
        db.query(Amenity)
        .filter(Amenity.id == amenity_id)
        .first()
    )

    if amenity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Amenity not found",
        )

    return amenity


# Admin-only amenity catalog management


@router.post(
    "",
    response_model=AmenityResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_amenity(
    amenity_data: AmenityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    existing = (
        db.query(Amenity)
        .filter(Amenity.name == amenity_data.name)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An amenity with this name already exists",
        )

    amenity = Amenity(**amenity_data.model_dump())

    try:
        db.add(amenity)
        db.commit()
        db.refresh(amenity)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An amenity with this name already exists",
        )

    return amenity


@router.get("", response_model=list[AmenityResponse])
def list_amenities(
    db: Session = Depends(get_db),
):
    return db.query(Amenity).order_by(Amenity.name).all()


@router.patch("/{amenity_id}", response_model=AmenityResponse)
def update_amenity(
    amenity_id: int,
    amenity_data: AmenityUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)
    amenity = get_amenity(amenity_id, db)
    update_data = amenity_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if value is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field} cannot be null",
            )

    if "name" in update_data:
        duplicate = (
            db.query(Amenity)
            .filter(
                Amenity.name == update_data["name"],
                Amenity.id != amenity_id,
            )
            .first()
        )

        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An amenity with this name already exists",
            )

    for field, value in update_data.items():
        setattr(amenity, field, value)

    try:
        db.commit()
        db.refresh(amenity)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An amenity with this name already exists",
        )

    return amenity


@router.delete(
    "/{amenity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_amenity(
    amenity_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)
    amenity = get_amenity(amenity_id, db)

    db.delete(amenity)
    db.commit()

    return None


# Hotel owner association and removal


@router.post(
    "/hotels/{hotel_id}/{amenity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def associate_amenity(
    hotel_id: int,
    amenity_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hotel = get_owned_hotel(hotel_id, current_user, db)
    amenity = get_amenity(amenity_id, db)

    already_associated = (
        db.query(hotel_amenities)
        .filter(
            hotel_amenities.c.hotel_id == hotel.id,
            hotel_amenities.c.amenity_id == amenity.id,
        )
        .first()
    )

    if already_associated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This amenity is already associated with the hotel",
        )

    try:
        db.execute(
            hotel_amenities.insert().values(
                hotel_id=hotel.id,
                amenity_id=amenity.id,
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This amenity is already associated with the hotel",
        )

    return None


@router.delete(
    "/hotels/{hotel_id}/{amenity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_amenity(
    hotel_id: int,
    amenity_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hotel = get_owned_hotel(hotel_id, current_user, db)
    get_amenity(amenity_id, db)

    result = db.execute(
        hotel_amenities.delete().where(
            hotel_amenities.c.hotel_id == hotel.id,
            hotel_amenities.c.amenity_id == amenity_id,
        )
    )

    if result.rowcount == 0:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Amenity is not associated with this hotel",
        )

    db.commit()
    return None


# Public filtering MUST be registered before /hotels/{hotel_id}


@router.get("/hotels/search")
def filter_hotels_by_amenities(
    amenity_ids: list[int] = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    requested_ids = set(amenity_ids)

    if len(requested_ids) != len(amenity_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Do not provide duplicate amenity IDs",
        )

    existing_ids = {
        row[0]
        for row in (
            db.query(Amenity.id)
            .filter(Amenity.id.in_(requested_ids))
            .all()
        )
    }

    if existing_ids != requested_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more amenity IDs do not exist",
        )

    matching_hotel_ids = (
        db.query(hotel_amenities.c.hotel_id)
        .filter(
            hotel_amenities.c.amenity_id.in_(requested_ids)
        )
        .group_by(hotel_amenities.c.hotel_id)
        .having(
            func.count(hotel_amenities.c.amenity_id)
            == len(requested_ids)
        )
        .subquery()
    )

    hotels = (
        db.query(Hotel)
        .join(
            matching_hotel_ids,
            matching_hotel_ids.c.hotel_id == Hotel.id,
        )
        .filter(Hotel.status == "APPROVED")
        .order_by(Hotel.name)
        .all()
    )

    return [
        {
            "id": hotel.id,
            "name": hotel.name,
            "city": hotel.city,
            "state": hotel.state,
            "country": hotel.country,
        }
        for hotel in hotels
    ]


# Retrieve amenities belonging to a hotel


@router.get(
    "/hotels/{hotel_id}",
    response_model=list[AmenityResponse],
)
def get_hotel_amenities(
    hotel_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hotel = get_owned_hotel(hotel_id, current_user, db)

    return (
        db.query(Amenity)
        .join(
            hotel_amenities,
            hotel_amenities.c.amenity_id == Amenity.id,
        )
        .filter(hotel_amenities.c.hotel_id == hotel.id)
        .order_by(Amenity.name)
        .all()
    )
