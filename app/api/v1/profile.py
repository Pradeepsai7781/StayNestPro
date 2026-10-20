import os
from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.profile import (
    CustomerProfileResponse,
    CustomerProfileUpdate,
)

router = APIRouter(prefix="/profile", tags=["Customer Profile"])

PROFILE_PICTURE_DIR = Path("media/profile_pictures")
MAX_PROFILE_PICTURE_SIZE = 5 * 1024 * 1024
ALLOWED_PROFILE_PICTURE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def require_customer(user: User) -> None:
    if user.role != UserRole.CUSTOMER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is available to customers only",
        )


@router.post(
    "/me",
    response_model=CustomerProfileResponse,
    status_code=status.HTTP_200_OK,
)
def create_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_customer(current_user)

    # Registration already creates the user's profile in the users table.
    # This endpoint returns that existing profile instead of creating
    # a duplicate user account.
    db.refresh(current_user)
    return current_user


@router.get("/me", response_model=CustomerProfileResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    require_customer(current_user)
    return current_user


@router.patch("/me", response_model=CustomerProfileResponse)
def update_my_profile(
    profile_data: CustomerProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_customer(current_user)

    updates = profile_data.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one field to update",
        )

    for field, value in updates.items():
        if isinstance(value, str):
            value = value.strip()

        if field == "full_name" and (
            value is None or not value
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Full name cannot be empty",
            )

        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)

    return current_user


@router.delete("/me", status_code=status.HTTP_200_OK)
def delete_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_customer(current_user)

    # Keep the account and its authentication records intact.
    # Clear only customer profile information.
    current_user.phone_number = None
    current_user.address = None
    current_user.city = None
    current_user.state = None
    current_user.postal_code = None
    current_user.country = None
    current_user.travel_preferences = None

    if current_user.profile_picture:
        picture_path = Path(current_user.profile_picture)
        try:
            if picture_path.is_file():
                picture_path.unlink()
        except OSError:
            pass

    current_user.profile_picture = None

    db.commit()

    return {
        "success": True,
        "message": "Customer profile information deleted successfully",
    }


@router.get("/me/preferences")
def get_my_preferences(
    current_user: User = Depends(get_current_user),
):
    require_customer(current_user)

    return {
        "success": True,
        "travel_preferences": current_user.travel_preferences or {},
    }


@router.put("/me/preferences")
def update_my_preferences(
    preferences: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_customer(current_user)

    if len(preferences) > 50:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Travel preferences cannot contain more than 50 entries",
        )

    current_user.travel_preferences = preferences
    db.commit()
    db.refresh(current_user)

    return {
        "success": True,
        "message": "Travel preferences saved successfully",
        "travel_preferences": current_user.travel_preferences or {},
    }


@router.post("/me/picture", response_model=CustomerProfileResponse)
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_customer(current_user)

    extension = ALLOWED_PROFILE_PICTURE_TYPES.get(file.content_type or "")
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPEG, PNG, and WebP profile pictures are allowed",
        )

    content = await file.read(MAX_PROFILE_PICTURE_SIZE + 1)
    await file.close()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty",
        )

    if len(content) > MAX_PROFILE_PICTURE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Profile picture must not exceed 5 MB",
        )

    # Check file signatures instead of trusting the content type alone.
    valid_signature = (
        (extension == ".jpg" and content.startswith(b"\xff\xd8\xff"))
        or (
            extension == ".png"
            and content.startswith(b"\x89PNG\r\n\x1a\n")
        )
        or (
            extension == ".webp"
            and content.startswith(b"RIFF")
            and content[8:12] == b"WEBP"
        )
    )

    if not valid_signature:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="The file content does not match a supported image format",
        )

    PROFILE_PICTURE_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"{current_user.id}_{uuid4().hex}{extension}"
    destination = PROFILE_PICTURE_DIR / filename

    try:
        destination.write_bytes(content)

        old_picture = current_user.profile_picture
        current_user.profile_picture = str(destination).replace("\\", "/")
        db.commit()
        db.refresh(current_user)

        if old_picture:
            old_path = Path(old_picture)
            if old_path != destination and old_path.is_file():
                try:
                    old_path.unlink()
                except OSError:
                    pass

    except Exception:
        db.rollback()
        if destination.exists():
            destination.unlink()
        raise

    return current_user
