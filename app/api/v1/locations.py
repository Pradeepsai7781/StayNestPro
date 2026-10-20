
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Hotel, HotelStatus
from app.schemas.location import (
    CoordinatesResponse,
    NearbyAttractionsResponse,
)
from app.services.location_service import (
    calculate_distance_km,
    get_nearby_attractions,
)


router = APIRouter(prefix="/hotels", tags=["Location Services"])


@router.get(
    "/{hotel_id}/coordinates",
    response_model=CoordinatesResponse,
)
def get_hotel_coordinates(
    hotel_id: int,
    db: Session = Depends(get_db),
):
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
            detail="Hotel not found",
        )

    if hotel.latitude is None or hotel.longitude is None:
        raise HTTPException(
            status_code=409,
            detail="Coordinates have not been set for this hotel",
        )

    return {
        "latitude": hotel.latitude,
        "longitude": hotel.longitude,
    }


@router.get(
    "/{hotel_id}/nearby-attractions",
    response_model=NearbyAttractionsResponse,
)
async def find_nearby_attractions(
    hotel_id: int,
    radius_m: int = Query(default=5000, ge=100, le=50000),
    db: Session = Depends(get_db),
):
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
            detail="Hotel not found",
        )

    if hotel.latitude is None or hotel.longitude is None:
        raise HTTPException(
            status_code=409,
            detail="Coordinates have not been set for this hotel",
        )

    try:
        attractions = await get_nearby_attractions(
            latitude=hotel.latitude,
            longitude=hotel.longitude,
            radius_m=radius_m,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    return {
        "hotel_id": hotel.id,
        "radius_m": radius_m,
        "attractions": attractions,
    }


@router.get("/{hotel_id}/distance")
def calculate_hotel_distance(
    hotel_id: int,
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    db: Session = Depends(get_db),
):
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
            detail="Hotel not found",
        )

    if hotel.latitude is None or hotel.longitude is None:
        raise HTTPException(
            status_code=409,
            detail="Coordinates have not been set for this hotel",
        )

    try:
        distance_km = calculate_distance_km(
            latitude,
            longitude,
            hotel.latitude,
            hotel.longitude,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return {
        "hotel_id": hotel.id,
        "distance_km": distance_km,
    }
