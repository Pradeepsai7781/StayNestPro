from calendar import monthrange
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import Hotel, Reservation, ReservationStatus, Room, User, UserRole
from app.models.payment import Payment, PaymentStatus
from app.services.revenue_analytics_service import get_revenue_for_period
from app.services.occupancy_analytics_service import get_occupancy_summary

router = APIRouter(prefix="/business-intelligence", tags=["Business Intelligence"])


def require_admin(user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only administrators can access business intelligence.")


def _growth(current: int | Decimal, previous: int | Decimal) -> float:
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round((float(current - previous) / float(previous)) * 100, 2)


@router.get("/growth")
def booking_and_revenue_growth(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    if (end_date - start_date).days > 365:
        raise HTTPException(status_code=422, detail="Date range cannot exceed 366 days.")
    days = (end_date - start_date).days + 1
    previous_end = start_date - timedelta(days=1)
    previous_start = previous_end - timedelta(days=days - 1)
    current_revenue = get_revenue_for_period(db, start_date, end_date)
    previous_revenue = get_revenue_for_period(db, previous_start, previous_end)
    current_bookings = db.query(Reservation).filter(
        Reservation.created_at >= datetime.combine(start_date, time.min),
        Reservation.created_at < datetime.combine(end_date + timedelta(days=1), time.min),
        Reservation.status.in_([ReservationStatus.CONFIRMED, ReservationStatus.COMPLETED]),
    ).count()
    previous_bookings = db.query(Reservation).filter(
        Reservation.created_at >= datetime.combine(previous_start, time.min),
        Reservation.created_at < datetime.combine(previous_end + timedelta(days=1), time.min),
        Reservation.status.in_([ReservationStatus.CONFIRMED, ReservationStatus.COMPLETED]),
    ).count()
    current_customers = db.query(User).filter(
        User.role == UserRole.CUSTOMER,
        User.created_at >= datetime.combine(start_date, time.min),
        User.created_at < datetime.combine(end_date + timedelta(days=1), time.min),
    ).count()
    previous_customers = db.query(User).filter(
        User.role == UserRole.CUSTOMER,
        User.created_at >= datetime.combine(previous_start, time.min),
        User.created_at < datetime.combine(previous_end + timedelta(days=1), time.min),
    ).count()
    return {
        "current_period": {"start_date": start_date, "end_date": end_date},
        "previous_period": {"start_date": previous_start, "end_date": previous_end},
        "booking_count": current_bookings,
        "previous_booking_count": previous_bookings,
        "booking_growth_percent": _growth(current_bookings, previous_bookings),
        "new_customer_count": current_customers,
        "previous_new_customer_count": previous_customers,
        "customer_growth_percent": _growth(current_customers, previous_customers),
        "revenue": current_revenue["net_revenue"],
        "previous_revenue": previous_revenue["net_revenue"],
        "revenue_growth_percent": _growth(current_revenue["net_revenue"], previous_revenue["net_revenue"]),
    }


@router.get("/top-hotels")
def top_performing_hotels(
    start_date: date = Query(...),
    end_date: date = Query(...),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    rows = (
        db.query(Hotel.id, Hotel.name, Hotel.city, Hotel.country,
                 func.count(func.distinct(Reservation.id)).label("booking_count"),
                 func.coalesce(func.sum(Payment.amount), 0).label("revenue"))
        .join(Room, Room.hotel_id == Hotel.id)
        .join(Reservation, Reservation.room_id == Room.id)
        .outerjoin(Payment, (Payment.reservation_id == Reservation.id) & (Payment.status == PaymentStatus.SUCCEEDED))
        .filter(Reservation.created_at >= datetime.combine(start_date, time.min),
                Reservation.created_at < datetime.combine(end_date + timedelta(days=1), time.min),
                Reservation.status.in_([ReservationStatus.CONFIRMED, ReservationStatus.COMPLETED]))
        .group_by(Hotel.id, Hotel.name, Hotel.city, Hotel.country)
        .order_by(func.coalesce(func.sum(Payment.amount), 0).desc(), func.count(func.distinct(Reservation.id)).desc())
        .limit(limit).all()
    )
    return [{"hotel_id": r.id, "hotel_name": r.name, "city": r.city, "country": r.country,
             "booking_count": r.booking_count, "revenue": Decimal(str(r.revenue or 0))} for r in rows]


@router.get("/top-destinations")
def top_destinations(
    start_date: date = Query(...),
    end_date: date = Query(...),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    rows = (
        db.query(Hotel.city, Hotel.country,
                 func.count(func.distinct(Reservation.id)).label("booking_count"),
                 func.count(func.distinct(Reservation.customer_id)).label("customer_count"))
        .join(Room, Room.hotel_id == Hotel.id)
        .join(Reservation, Reservation.room_id == Room.id)
        .filter(Reservation.created_at >= datetime.combine(start_date, time.min),
                Reservation.created_at < datetime.combine(end_date + timedelta(days=1), time.min),
                Reservation.status.in_([ReservationStatus.CONFIRMED, ReservationStatus.COMPLETED]))
        .group_by(Hotel.city, Hotel.country)
        .order_by(func.count(func.distinct(Reservation.id)).desc())
        .limit(limit).all()
    )
    return [{"city": r.city, "country": r.country, "booking_count": r.booking_count,
             "customer_count": r.customer_count} for r in rows]


@router.get("/occupancy-trends")
def occupancy_trends(
    start_date: date = Query(...),
    end_date: date = Query(...),
    hotel_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    if (end_date - start_date).days > 365:
        raise HTTPException(status_code=422, detail="Date range cannot exceed 366 days.")
    return get_occupancy_summary(db=db, start_date=start_date, end_date=end_date, hotel_id=hotel_id)


@router.get("/monthly-summary")
def monthly_business_summary(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    start_date = date(year, month, 1)
    end_date = date(year, month, monthrange(year, month)[1])
    revenue = get_revenue_for_period(db, start_date, end_date)
    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date + timedelta(days=1), time.min)
    bookings = db.query(Reservation).filter(Reservation.created_at >= start_dt, Reservation.created_at < end_dt).count()
    new_customers = db.query(User).filter(User.role == UserRole.CUSTOMER, User.created_at >= start_dt, User.created_at < end_dt).count()
    occupancy = get_occupancy_summary(db=db, start_date=start_date, end_date=end_date, hotel_id=None)
    return {"year": year, "month": month, "period_start": start_date, "period_end": end_date,
            "revenue": revenue, "booking_count": bookings, "new_customer_count": new_customers,
            "occupancy": occupancy}
