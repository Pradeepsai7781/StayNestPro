
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.jwt import decode_token
from app.db.session import get_db
from app.models import (
    Hotel,
    HotelStatus,
    HotelImage,
    HotelVerificationDocument,
    User,
    UserRole,
)
from app.schemas.hotel import (
    HotelCreate,
    HotelResponse,
    HotelUpdate,
    HotelImageCreate,
    HotelImageUpdate,
    HotelImageResponse,
)


router = APIRouter(prefix="/hotels", tags=["Hotels"])
optional_bearer = HTTPBearer(auto_error=False)

DOCUMENT_DIRECTORY = Path("media") / "hotel_documents"
MAX_DOCUMENT_SIZE = 5 * 1024 * 1024

ALLOWED_DOCUMENT_TYPES = {
    "application/pdf": {".pdf"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
}

ALLOWED_DOCUMENT_CATEGORIES = {
    "BUSINESS_LICENSE",
    "TAX_CERTIFICATE",
    "IDENTITY_PROOF",
}


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None

    try:
        payload = decode_token(credentials.credentials)

        if payload.get("type") != "access":
            return None

        user_id = payload.get("sub")
        if user_id is None:
            return None

        user = db.query(User).filter(User.id == int(user_id)).first()

        if user is None or not user.is_active:
            return None

        return user
    except Exception:
        return None


def require_hotel_owner(user: User) -> None:
    if user.role != UserRole.HOTEL_OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only hotel owners can access this endpoint",
        )


def get_owned_hotel(hotel_id: int, owner_id: int, db: Session) -> Hotel:
    hotel = (
        db.query(Hotel)
        .filter(
            Hotel.id == hotel_id,
            Hotel.owner_id == owner_id,
        )
        .first()
    )

    if hotel is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hotel not found",
        )

    return hotel


def get_hotel_image(
    hotel_id: int,
    image_id: int,
    db: Session,
) -> HotelImage:
    image = (
        db.query(HotelImage)
        .filter(
            HotelImage.id == image_id,
            HotelImage.hotel_id == hotel_id,
        )
        .first()
    )

    if image is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hotel image not found",
        )

    return image


def validate_document_content(content_type: str, content: bytes) -> str:
    """Check file signatures instead of trusting the client content type."""

    if content_type == "application/pdf" and content.startswith(b"%PDF-"):
        return ".pdf"

    if content_type == "image/jpeg" and content.startswith(b"\xff\xd8\xff"):
        return ".jpg"

    if content_type == "image/png" and content.startswith(
        b"\x89PNG\r\n\x1a\n"
    ):
        return ".png"

    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail="Upload a valid PDF, JPEG, or PNG document",
    )


def set_primary_image(hotel_id: int, db: Session, exclude_image_id: int | None = None) -> None:
    """Clear the primary flag from other images belonging to this hotel."""

    query = db.query(HotelImage).filter(
        HotelImage.hotel_id == hotel_id,
        HotelImage.is_primary.is_(True),
    )

    if exclude_image_id is not None:
        query = query.filter(HotelImage.id != exclude_image_id)

    query.update(
        {HotelImage.is_primary: False},
        synchronize_session=False,
    )


@router.post("/", response_model=HotelResponse, status_code=201)
def register_hotel(
    hotel_data: HotelCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_hotel_owner(current_user)

    hotel = Hotel(
        **hotel_data.model_dump(),
        owner_id=current_user.id,
        status=HotelStatus.PENDING,
    )

    db.add(hotel)
    db.commit()
    db.refresh(hotel)

    return hotel


@router.get("/mine", response_model=list[HotelResponse])
def list_my_hotels(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_hotel_owner(current_user)

    return (
        db.query(Hotel)
        .filter(Hotel.owner_id == current_user.id)
        .order_by(Hotel.id)
        .all()
    )


@router.get("/{hotel_id}", response_model=HotelResponse)
def get_hotel(
    hotel_id: int,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()

    if hotel is None:
        raise HTTPException(status_code=404, detail="Hotel not found")

    is_owner = (
        current_user is not None
        and current_user.role == UserRole.HOTEL_OWNER
        and hotel.owner_id == current_user.id
    )

    if is_owner:
        return hotel

    if hotel.status != HotelStatus.APPROVED:
        raise HTTPException(status_code=404, detail="Hotel not found")

    return hotel


@router.patch("/{hotel_id}", response_model=HotelResponse)
def update_hotel(
    hotel_id: int,
    hotel_data: HotelUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_hotel_owner(current_user)

    hotel = get_owned_hotel(hotel_id, current_user.id, db)
    updates = hotel_data.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one field to update",
        )

    for field, value in updates.items():
        if isinstance(value, str):
            value = value.strip()

        if field == "name" and not value:
            raise HTTPException(
                status_code=422,
                detail="Hotel name cannot be empty",
            )

        setattr(hotel, field, value)

    db.commit()
    db.refresh(hotel)

    return hotel


@router.post(
    "/{hotel_id}/documents",
    status_code=status.HTTP_201_CREATED,
)
async def upload_hotel_document(
    hotel_id: int,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_hotel_owner(current_user)
    hotel = get_owned_hotel(hotel_id, current_user.id, db)

    document_type = document_type.strip().upper()

    if document_type not in ALLOWED_DOCUMENT_CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail=(
                "document_type must be BUSINESS_LICENSE, "
                "TAX_CERTIFICATE, or IDENTITY_PROOF"
            ),
        )

    original_filename = Path(file.filename or "document").name
    extension = Path(original_filename).suffix.lower()
    content_type = file.content_type or ""

    if extension not in ALLOWED_DOCUMENT_TYPES.get(content_type, set()):
        raise HTTPException(
            status_code=415,
            detail="Upload a PDF, JPEG, or PNG file with a matching file type",
        )

    content = await file.read(MAX_DOCUMENT_SIZE + 1)

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty",
        )

    if len(content) > MAX_DOCUMENT_SIZE:
        raise HTTPException(
            status_code=413,
            detail="The maximum document size is 5 MB",
        )

    validated_extension = validate_document_content(content_type, content)

    DOCUMENT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    generated_filename = (
        f"{hotel.id}_{uuid.uuid4().hex}{validated_extension}"
    )
    destination = DOCUMENT_DIRECTORY / generated_filename
    relative_path = destination.as_posix()

    try:
        with destination.open("xb") as destination_file:
            destination_file.write(content)

        document = HotelVerificationDocument(
            hotel_id=hotel.id,
            document_type=document_type,
            file_path=relative_path,
            original_filename=original_filename[:255],
            content_type=content_type,
        )

        db.add(document)
        db.commit()
        db.refresh(document)

    except Exception:
        db.rollback()

        if destination.exists():
            destination.unlink()

        raise

    finally:
        await file.close()

    return {
        "id": document.id,
        "hotel_id": document.hotel_id,
        "document_type": document.document_type,
        "original_filename": document.original_filename,
        "content_type": document.content_type,
        "uploaded_at": document.uploaded_at,
        "message": "Verification document uploaded successfully",
    }


@router.post(
    "/{hotel_id}/images",
    response_model=HotelImageResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_hotel_image(
    hotel_id: int,
    image_data: HotelImageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_hotel_owner(current_user)
    get_owned_hotel(hotel_id, current_user.id, db)

    if image_data.is_primary:
        set_primary_image(hotel_id, db)

    image = HotelImage(
        hotel_id=hotel_id,
        image_url=str(image_data.image_url),
        caption=image_data.caption,
        category=image_data.category,
        display_order=image_data.display_order,
        is_primary=image_data.is_primary,
    )

    try:
        db.add(image)
        db.commit()
        db.refresh(image)
    except Exception:
        db.rollback()
        raise

    return image


@router.get(
    "/{hotel_id}/images",
    response_model=list[HotelImageResponse],
)
def list_hotel_images(
    hotel_id: int,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    hotel = db.query(Hotel).filter(Hotel.id == hotel_id).first()

    if hotel is None:
        raise HTTPException(status_code=404, detail="Hotel not found")

    is_owner = (
        current_user is not None
        and current_user.role == UserRole.HOTEL_OWNER
        and current_user.id == hotel.owner_id
    )

    if hotel.status != HotelStatus.APPROVED and not is_owner:
        raise HTTPException(status_code=404, detail="Hotel not found")

    return (
        db.query(HotelImage)
        .filter(HotelImage.hotel_id == hotel_id)
        .order_by(
            HotelImage.is_primary.desc(),
            HotelImage.display_order.asc(),
            HotelImage.id.asc(),
        )
        .all()
    )


@router.patch(
    "/{hotel_id}/images/{image_id}",
    response_model=HotelImageResponse,
)
def update_hotel_image(
    hotel_id: int,
    image_id: int,
    image_data: HotelImageUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_hotel_owner(current_user)
    get_owned_hotel(hotel_id, current_user.id, db)

    image = get_hotel_image(hotel_id, image_id, db)
    updates = image_data.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one field to update",
        )

    if updates.get("is_primary") is True:
        set_primary_image(
            hotel_id,
            db,
            exclude_image_id=image_id,
        )

    for field, value in updates.items():
        if field == "image_url" and value is not None:
            value = str(value)

        if isinstance(value, str):
            value = value.strip()

        setattr(image, field, value)

    try:
        db.commit()
        db.refresh(image)
    except Exception:
        db.rollback()
        raise

    return image


@router.delete(
    "/{hotel_id}/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_hotel_image(
    hotel_id: int,
    image_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_hotel_owner(current_user)
    get_owned_hotel(hotel_id, current_user.id, db)

    image = get_hotel_image(hotel_id, image_id, db)

    db.delete(image)
    db.commit()

    return None
