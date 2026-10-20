
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.messaging import Conversation, Message
from app.models.user import User, UserRole
from app.schemas.messaging import (
    ConversationCreate,
    ConversationResponse,
    MessageCreate,
    MessagePage,
    MessageResponse,
)

router = APIRouter(
    prefix="/messaging",
    tags=["In-App Messaging"],
)


def ensure_participant(
    conversation: Conversation,
    user_id: int,
) -> None:
    """Allow access only to the two participants in a conversation."""
    if user_id not in (
        conversation.customer_id,
        conversation.participant_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this conversation.",
        )


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a customer-to-hotel or customer-to-support conversation."""
    if current_user.role != UserRole.CUSTOMER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can start conversations.",
        )

    if payload.conversation_type == "SUPPORT":
        participant = (
            db.query(User)
            .filter(
                User.role == UserRole.ADMIN,
                User.is_active.is_(True),
            )
            .order_by(User.id)
            .first()
        )

        if participant is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Support is currently unavailable.",
            )

    else:
        if payload.participant_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="participant_id is required for hotel conversations.",
            )

        participant = (
            db.query(User)
            .filter(
                User.id == payload.participant_id,
                User.role.in_(
                    [UserRole.HOTEL_OWNER, UserRole.HOTEL_STAFF]
                ),
                User.is_active.is_(True),
            )
            .first()
        )

        if participant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active hotel owner or staff member not found.",
            )

    conversation = Conversation(
        customer_id=current_user.id,
        participant_id=participant.id,
        conversation_type=payload.conversation_type,
        subject=payload.subject,
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation


@router.get(
    "/conversations",
    response_model=list[ConversationResponse],
)
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List conversations in which the current user participates."""
    return (
        db.query(Conversation)
        .filter(
            or_(
                Conversation.customer_id == current_user.id,
                Conversation.participant_id == current_user.id,
            )
        )
        .order_by(
            Conversation.updated_at.desc(),
            Conversation.id.desc(),
        )
        .all()
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def send_message(
    conversation_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a message to another participant in a conversation."""
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    ensure_participant(conversation, current_user.id)

    content = payload.content.strip()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be empty.",
        )

    message = Message(
        conversation_id=conversation.id,
        sender_id=current_user.id,
        content=content,
        status="SENT",
    )

    conversation.updated_at = datetime.now(timezone.utc)

    db.add(message)
    db.commit()
    db.refresh(message)

    return message


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessagePage,
)
def list_messages(
    conversation_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve paginated messages and mark received messages as read."""
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    ensure_participant(conversation, current_user.id)

    unread_query = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.sender_id != current_user.id,
        Message.status == "SENT",
    )

    unread_count = unread_query.count()

    if unread_count:
        unread_query.update(
            {
                "status": "READ",
                "read_at": datetime.now(timezone.utc),
            },
            synchronize_session=False,
        )
        db.commit()

    messages_query = db.query(Message).filter(
        Message.conversation_id == conversation_id
    )

    total = messages_query.count()

    items = (
        messages_query
        .order_by(Message.created_at.asc(), Message.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return MessagePage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        unread_count=unread_count,
    )
