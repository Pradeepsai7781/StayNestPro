
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.db.session import get_db
from app.models import (
    Payment,
    Reservation,
    Room,
    Hotel,
    SupportConversation,
    User,
    UserRole,
)
from app.services.support_chatbot_service import generate_support_answer

router = APIRouter(prefix="/support", tags=["AI Customer Support"])

require_customer = require_roles(UserRole.CUSTOMER)


class SupportQuestion(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    category: str = Field(
        default="general",
        pattern="^(hotel|booking|payment|cancellation|general)$",
    )
    reservation_id: int | None = Field(default=None, gt=0)


@router.post("/chat")
def chat_with_support(
    request: SupportQuestion,
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    context = {}
    reservation = None

    if request.reservation_id is not None:
        reservation = (
            db.query(Reservation)
            .filter(
                Reservation.id == request.reservation_id,
                Reservation.customer_id == current_user.id,
            )
            .first()
        )

        if not reservation:
            raise HTTPException(
                status_code=404,
                detail="Reservation not found.",
            )

        room = db.query(Room).filter(Room.id == reservation.room_id).first()
        hotel = (
            db.query(Hotel).filter(Hotel.id == room.hotel_id).first()
            if room else None
        )

        context["reservation"] = {
            "reservation_id": reservation.id,
            "booking_reference": reservation.booking_reference,
            "status": reservation.status.value,
            "check_in": reservation.check_in.isoformat(),
            "check_out": reservation.check_out.isoformat(),
            "total_price": str(reservation.total_price),
            "hotel_name": hotel.name if hotel else None,
        }

        if request.category == "payment":
            payments = (
                db.query(Payment)
                .filter(
                    Payment.reservation_id == reservation.id,
                    Payment.customer_id == current_user.id,
                )
                .all()
            )
            context["payments"] = [
                {
                    "status": payment.status.value,
                    "amount": str(payment.amount),
                    "currency": payment.currency,
                }
                for payment in payments
            ]

    answer = generate_support_answer(
        question=request.question,
        category=request.category,
        context=context,
    )

    conversation = SupportConversation(
        user_id=current_user.id,
        category=request.category,
        question=request.question,
        answer=answer,
        reservation_id=reservation.id if reservation else None,
        context=context,
    )

    try:
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    except Exception:
        db.rollback()
        raise

    return {
        "conversation_id": conversation.id,
        "category": conversation.category,
        "answer": conversation.answer,
        "created_at": conversation.created_at,
    }


@router.get("/conversations")
def get_support_conversations(
    current_user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    conversations = (
        db.query(SupportConversation)
        .filter(SupportConversation.user_id == current_user.id)
        .order_by(SupportConversation.created_at.desc())
        .all()
    )

    return {
        "count": len(conversations),
        "conversations": [
            {
                "conversation_id": item.id,
                "category": item.category,
                "question": item.question,
                "answer": item.answer,
                "reservation_id": item.reservation_id,
                "created_at": item.created_at,
            }
            for item in conversations
        ],
    }
