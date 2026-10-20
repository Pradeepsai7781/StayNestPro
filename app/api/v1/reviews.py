
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import (
    Hotel,
    HotelReview,
    Reservation,
    ReservationStatus,
    Room,
    User,
    UserRole,
)
from app.schemas.review import (
    HotelReviewCreate,
    HotelReviewUpdate,
    HotelReviewResponse,
    HotelReviewReport,
)


router = APIRouter(prefix="/reviews", tags=["Reviews"])


def require_customer(user: User) -> None:
    if user.role != UserRole.CUSTOMER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can perform this action",
        )


def require_admin(user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can moderate reviews",
        )


def get_review(review_id: int, db: Session) -> HotelReview:
    review = (
        db.query(HotelReview)
        .filter(HotelReview.id == review_id)
        .first()
    )

    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found",
        )

    return review


def update_hotel_rating(hotel_id: int, db: Session) -> None:
    average_rating = (
        db.query(func.avg(HotelReview.rating))
        .filter(
            HotelReview.hotel_id == hotel_id,
            HotelReview.is_hidden.is_(False),
        )
        .scalar()
    )

    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()

    if hotel is not None:
        hotel.rating = (
            round(float(average_rating), 2)
            if average_rating is not None
            else None
        )


# Create a review for a completed stay

@router.post(
    "",
    response_model=HotelReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_review(
    review_data: HotelReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_customer(current_user)

    reservation = (
        db.query(Reservation)
        .filter(
            Reservation.id == review_data.reservation_id,
            Reservation.customer_id == current_user.id,
        )
        .first()
    )

    if reservation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found for this customer",
        )

    if reservation.status != ReservationStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only completed stays can be reviewed",
        )

    room = db.query(Room).filter(Room.id == reservation.room_id).first()

    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation room not found",
        )

    existing_review = (
        db.query(HotelReview)
        .filter(HotelReview.reservation_id == reservation.id)
        .first()
    )

    if existing_review:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This stay has already been reviewed",
        )

    review = HotelReview(
        reservation_id=reservation.id,
        hotel_id=room.hotel_id,
        user_id=current_user.id,
        rating=review_data.rating,
        comment=review_data.comment,
    )

    try:
        db.add(review)
        db.flush()
        update_hotel_rating(room.hotel_id, db)
        db.commit()
        db.refresh(review)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This stay has already been reviewed",
        )

    return review


# List visible reviews for a hotel

@router.get(
    "/hotels/{hotel_id}",
    response_model=list[HotelReviewResponse],
)
def list_hotel_reviews(
    hotel_id: int,
    db: Session = Depends(get_db),
):
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()

    if hotel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hotel not found",
        )

    return (
        db.query(HotelReview)
        .filter(
            HotelReview.hotel_id == hotel_id,
            HotelReview.is_hidden.is_(False),
        )
        .order_by(HotelReview.created_at.desc())
        .all()
    )


# Retrieve a hotel's average rating

@router.get("/hotels/{hotel_id}/rating")
def get_hotel_rating(
    hotel_id: int,
    db: Session = Depends(get_db),
):
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()

    if hotel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hotel not found",
        )

    average_rating = (
        db.query(func.avg(HotelReview.rating))
        .filter(
            HotelReview.hotel_id == hotel_id,
            HotelReview.is_hidden.is_(False),
        )
        .scalar()
    )

    review_count = (
        db.query(HotelReview)
        .filter(
            HotelReview.hotel_id == hotel_id,
            HotelReview.is_hidden.is_(False),
        )
        .count()
    )

    return {
        "hotel_id": hotel_id,
        "average_rating": (
            round(float(average_rating), 2)
            if average_rating is not None
            else None
        ),
        "review_count": review_count,
    }


# Update your own review

@router.patch("/{review_id}", response_model=HotelReviewResponse)
def update_review(
    review_id: int,
    review_data: HotelReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_customer(current_user)
    review = get_review(review_id, db)

    if review.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own reviews",
        )

    if review.is_hidden:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A moderated review cannot be updated",
        )

    update_data = review_data.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide at least one field to update",
        )

    for field, value in update_data.items():
        setattr(review, field, value)

    update_hotel_rating(review.hotel_id, db)
    db.commit()
    db.refresh(review)

    return review


# Delete your own review

@router.delete(
    "/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_review(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_customer(current_user)
    review = get_review(review_id, db)

    if review.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own reviews",
        )

    hotel_id = review.hotel_id

    db.delete(review)
    update_hotel_rating(hotel_id, db)
    db.commit()

    return None


# Report a review for moderation

@router.post("/{review_id}/report")
def report_review(
    review_id: int,
    report_data: HotelReviewReport,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_customer(current_user)
    review = get_review(review_id, db)

    if review.user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot report your own review",
        )

    if review.is_reported:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This review has already been reported",
        )

    review.is_reported = True
    review.report_reason = report_data.reason

    db.commit()
    db.refresh(review)

    return {
        "message": "Review reported successfully",
        "review_id": review.id,
        "report_reason": review.report_reason,
    }


# List reported reviews for administrators

@router.get(
    "/moderation/reported",
    response_model=list[HotelReviewResponse],
)
def list_reported_reviews(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    return (
        db.query(HotelReview)
        .filter(HotelReview.is_reported.is_(True))
        .order_by(HotelReview.created_at.desc())
        .all()
    )


# Hide or restore a reported review

@router.patch(
    "/{review_id}/moderate",
    response_model=HotelReviewResponse,
)
def moderate_review(
    review_id: int,
    hide: bool,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)
    review = get_review(review_id, db)

    if not review.is_reported:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only reported reviews can be moderated",
        )

    review.is_hidden = hide
    update_hotel_rating(review.hotel_id, db)
    db.commit()
    db.refresh(review)

    return review
