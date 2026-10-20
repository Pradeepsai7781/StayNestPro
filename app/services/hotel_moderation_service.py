
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import (
    Hotel,
    HotelReview,
    HotelStatus,
    HotelVerificationDocument,
)


def get_hotel_verification_documents(
    db: Session,
    hotel_id: int | None = None,
) -> list[dict]:
    query = db.query(HotelVerificationDocument)

    if hotel_id is not None:
        query = query.filter(
            HotelVerificationDocument.hotel_id == hotel_id
        )

    documents = query.order_by(
        HotelVerificationDocument.uploaded_at.desc()
    ).all()

    return [
        {
            "id": document.id,
            "hotel_id": document.hotel_id,
            "document_type": document.document_type,
            "original_filename": document.original_filename,
            "content_type": document.content_type,
            "uploaded_at": document.uploaded_at,
        }
        for document in documents
    ]


def moderate_hotel(
    db: Session,
    hotel_id: int,
    decision: HotelStatus,
    reason: str,
    admin_id: int,
) -> dict:
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()

    if hotel is None:
        raise HTTPException(status_code=404, detail="Hotel not found")

    if decision not in (
        HotelStatus.APPROVED,
        HotelStatus.REJECTED,
        HotelStatus.SUSPENDED,
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid moderation decision",
        )

    if not reason.strip():
        raise HTTPException(
            status_code=400,
            detail="A decision reason is required",
        )

    hotel.status = decision
    hotel.decision_reason = reason.strip()
    hotel.decision_by = admin_id
    hotel.decision_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(hotel)

    return {
        "hotel_id": hotel.id,
        "hotel_name": hotel.name,
        "status": hotel.status.value,
        "decision_reason": hotel.decision_reason,
        "decision_by": hotel.decision_by,
        "decision_at": hotel.decision_at,
    }


def get_reported_reviews(
    db: Session,
    hotel_id: int | None = None,
) -> list[dict]:
    query = db.query(HotelReview).filter(
        HotelReview.is_reported.is_(True)
    )

    if hotel_id is not None:
        query = query.filter(HotelReview.hotel_id == hotel_id)

    reviews = query.order_by(HotelReview.created_at.desc()).all()

    return [
        {
            "id": review.id,
            "hotel_id": review.hotel_id,
            "rating": review.rating,
            "comment": review.comment,
            "report_reason": review.report_reason,
            "is_reported": review.is_reported,
            "is_hidden": review.is_hidden,
            "created_at": review.created_at,
        }
        for review in reviews
    ]


def moderate_reported_review(
    db: Session,
    review_id: int,
    hide: bool,
) -> dict:
    review = (
        db.query(HotelReview)
        .filter(HotelReview.id == review_id)
        .first()
    )

    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")

    review.is_hidden = hide
    db.commit()
    db.refresh(review)

    return {
        "id": review.id,
        "hotel_id": review.hotel_id,
        "is_reported": review.is_reported,
        "is_hidden": review.is_hidden,
        "report_reason": review.report_reason,
    }


def get_reported_properties(db: Session) -> list[dict]:
    hotels = (
        db.query(Hotel)
        .filter(Hotel.is_reported.is_(True))
        .order_by(Hotel.updated_at.desc())
        .all()
    )

    return [
        {
            "hotel_id": hotel.id,
            "hotel_name": hotel.name,
            "status": hotel.status.value,
            "is_reported": hotel.is_reported,
            "report_reason": hotel.report_reason,
            "decision_reason": hotel.decision_reason,
            "decision_by": hotel.decision_by,
            "decision_at": hotel.decision_at,
        }
        for hotel in hotels
    ]


def moderate_reported_property(
    db: Session,
    hotel_id: int,
    reason: str,
    admin_id: int,
    suspend: bool,
) -> dict:
    hotel = (
        db.query(Hotel)
        .filter(
            Hotel.id == hotel_id,
            Hotel.is_reported.is_(True),
        )
        .first()
    )

    if hotel is None:
        raise HTTPException(
            status_code=404,
            detail="Reported property not found",
        )

    if not reason.strip():
        raise HTTPException(
            status_code=400,
            detail="A decision reason is required",
        )

    if suspend:
        hotel.status = HotelStatus.SUSPENDED

    hotel.decision_reason = reason.strip()
    hotel.decision_by = admin_id
    hotel.decision_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(hotel)

    return {
        "hotel_id": hotel.id,
        "hotel_name": hotel.name,
        "status": hotel.status.value,
        "is_reported": hotel.is_reported,
        "report_reason": hotel.report_reason,
        "decision_reason": hotel.decision_reason,
        "decision_by": hotel.decision_by,
        "decision_at": hotel.decision_at,
    }
