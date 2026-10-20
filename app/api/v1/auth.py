
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from jwt.exceptions import InvalidTokenError
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    status,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.permissions import require_roles
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models import AuthToken, User, UserRole, RefreshToken
from app.models.audit_log import AuditEventType
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    UserResponse,
    TokenResponse,
    RefreshTokenRequest,
)
from app.schemas.auth_tokens import (
    EmailRequest,
    TokenVerificationRequest,
    PasswordResetRequest,
)
from app.services.audit_log_service import record_audit_event
from app.services.email_service import send_email


router = APIRouter(prefix="/auth", tags=["Authentication"])

VERIFICATION_PURPOSE = "email_verification"
RESET_PURPOSE = "password_reset"
VERIFICATION_EXPIRE_HOURS = 24
RESET_EXPIRE_MINUTES = 30

logger = logging.getLogger(__name__)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_auth_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _send_email_safely(
    recipient: str,
    subject: str,
    body: str,
) -> None:
    """Prevent temporary email failures from breaking API requests."""
    try:
        send_email(recipient, subject, body)
    except Exception:
        logger.exception("Email delivery failed.")


def _record_auth_audit_safely(
    db: Session,
    request: Request,
    event_type: AuditEventType,
    action: str,
    actor_id: int | None = None,
    description: str | None = None,
) -> None:
    """Record authentication events without exposing credentials."""
    try:
        record_audit_event(
            db=db,
            event_type=event_type,
            action=action,
            actor_id=actor_id,
            description=description,
            entity_type="User" if actor_id is not None else None,
            entity_id=actor_id,
            ip_address=(
                request.client.host if request.client else None
            ),
        )
    except Exception:
        db.rollback()
        logger.exception(
            "Failed to record authentication audit event."
        )


def _create_auth_token(
    db: Session,
    user_id: int,
    purpose: str,
    lifetime: timedelta,
) -> str:
    previous_tokens = (
        db.query(AuthToken)
        .filter(
            AuthToken.user_id == user_id,
            AuthToken.purpose == purpose,
            AuthToken.used_at.is_(None),
        )
        .all()
    )

    now = _now_utc()

    for previous in previous_tokens:
        previous.used_at = now.replace(tzinfo=None)

    raw_token = secrets.token_urlsafe(32)

    db.add(
        AuthToken(
            user_id=user_id,
            token_hash=hash_auth_token(raw_token),
            purpose=purpose,
            expires_at=(now + lifetime).replace(tzinfo=None),
        )
    )

    db.commit()
    return raw_token


def _get_valid_auth_token(
    db: Session,
    raw_token: str,
    purpose: str,
) -> AuthToken:
    invalid_token = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired token",
    )

    token_record = (
        db.query(AuthToken)
        .filter(
            AuthToken.token_hash == hash_auth_token(raw_token),
            AuthToken.purpose == purpose,
        )
        .first()
    )

    if token_record is None or token_record.used_at is not None:
        raise invalid_token

    if _as_utc(token_record.expires_at) <= _now_utc():
        raise invalid_token

    return token_record


def save_refresh_token(
    db: Session,
    user_id: int,
    token: str,
) -> None:
    payload = decode_token(token)

    expires_at = datetime.fromtimestamp(
        payload["exp"],
        tz=timezone.utc,
    )

    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=hash_refresh_token(token),
            expires_at=expires_at.replace(tzinfo=None),
        )
    )


def issue_tokens(db: Session, user: User) -> TokenResponse:
    access_token = create_access_token(user.id, user.role.value)
    refresh_token = create_refresh_token(user.id)

    save_refresh_token(db, user.id, refresh_token)
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    user_data: UserRegister,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    email = str(user_data.email).lower()

    existing_user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        full_name=user_data.full_name.strip(),
        email=email,
        hashed_password=hash_password(user_data.password),
        role=UserRole.CUSTOMER,
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    try:
        verification_token = _create_auth_token(
            db,
            user.id,
            VERIFICATION_PURPOSE,
            timedelta(hours=VERIFICATION_EXPIRE_HOURS),
        )

        background_tasks.add_task(
            _send_email_safely,
            user.email,
            "Verify your StayNest Pro email",
            (
                f"Hello {user.full_name},\n\n"
                "Use the token below to verify your StayNest Pro "
                "email address.\n\n"
                f"{verification_token}\n\n"
                "This token expires in 24 hours and can only be "
                "used once.\n"
                "If you did not create this account, you can "
                "ignore this email."
            ),
        )
    except Exception:
        db.rollback()
        logger.exception(
            "Could not create an email verification token."
        )

    return user


@router.post("/login", response_model=TokenResponse)
def login_user(
    request: Request,
    login_data: UserLogin,
    db: Session = Depends(get_db),
):
    email = str(login_data.email).lower()

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if user is None or not verify_password(
        login_data.password,
        user.hashed_password if user is not None else "",
    ):
        _record_auth_audit_safely(
            db=db,
            request=request,
            event_type=AuditEventType.LOGIN_FAILED,
            action="LOGIN_FAILED",
            actor_id=user.id if user is not None else None,
            description="Login failed due to invalid credentials.",
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        _record_auth_audit_safely(
            db=db,
            request=request,
            event_type=AuditEventType.SECURITY_EVENT,
            action="LOGIN_INACTIVE_ACCOUNT",
            actor_id=user.id,
            description="Login rejected for an inactive account.",
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive",
        )

    try:
        result = issue_tokens(db, user)
    except Exception:
        db.rollback()
        raise

    _record_auth_audit_safely(
        db=db,
        request=request,
        event_type=AuditEventType.LOGIN,
        action="LOGIN",
        actor_id=user.id,
        description="User logged in successfully.",
    )

    return result


@router.post("/verify-email")
def verify_email(
    request: TokenVerificationRequest,
    db: Session = Depends(get_db),
):
    token_record = _get_valid_auth_token(
        db,
        request.token,
        VERIFICATION_PURPOSE,
    )

    user = (
        db.query(User)
        .filter(User.id == token_record.user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token",
        )

    now = _now_utc().replace(tzinfo=None)
    token_record.used_at = now
    user.is_email_verified = True
    db.commit()

    return {
        "success": True,
        "message": "Email verified successfully",
    }


@router.post("/resend-verification")
def resend_verification(
    request: EmailRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    response = {
        "success": True,
        "message": (
            "If an eligible account exists, a verification "
            "email will be sent."
        ),
    }

    email = str(request.email).lower()
    user = db.query(User).filter(User.email == email).first()

    if user is None or user.is_email_verified or not user.is_active:
        return response

    token = _create_auth_token(
        db,
        user.id,
        VERIFICATION_PURPOSE,
        timedelta(hours=VERIFICATION_EXPIRE_HOURS),
    )

    background_tasks.add_task(
        _send_email_safely,
        user.email,
        "Verify your StayNest Pro email",
        (
            f"Hello {user.full_name},\n\n"
            "Use this token to verify your StayNest Pro email "
            "address:\n\n"
            f"{token}\n\n"
            "This token expires in 24 hours and can only be "
            "used once."
        ),
    )

    return response


@router.post("/forgot-password")
def forgot_password(
    request: EmailRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    response = {
        "success": True,
        "message": (
            "If an account exists for this email, password-reset "
            "instructions will be sent."
        ),
    }

    email = str(request.email).lower()
    user = db.query(User).filter(User.email == email).first()

    if user is None or not user.is_active:
        return response

    token = _create_auth_token(
        db,
        user.id,
        RESET_PURPOSE,
        timedelta(minutes=RESET_EXPIRE_MINUTES),
    )

    background_tasks.add_task(
        _send_email_safely,
        user.email,
        "Reset your StayNest Pro password",
        (
            f"Hello {user.full_name},\n\n"
            "Use this token to reset your StayNest Pro password:\n\n"
            f"{token}\n\n"
            "This token expires in 30 minutes and can only be "
            "used once. If you did not request a password reset, "
            "you can ignore this email."
        ),
    )

    return response


@router.post("/reset-password")
def reset_password(
    request: PasswordResetRequest,
    db: Session = Depends(get_db),
):
    token_record = _get_valid_auth_token(
        db,
        request.token,
        RESET_PURPOSE,
    )

    user = (
        db.query(User)
        .filter(User.id == token_record.user_id)
        .first()
    )

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token",
        )

    now = _now_utc().replace(tzinfo=None)
    token_record.used_at = now
    user.hashed_password = hash_password(request.new_password)

    (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
        .update(
            {"revoked_at": now},
            synchronize_session=False,
        )
    )

    (
        db.query(AuthToken)
        .filter(
            AuthToken.user_id == user.id,
            AuthToken.used_at.is_(None),
        )
        .update(
            {"used_at": now},
            synchronize_session=False,
        )
    )

    db.commit()

    return {
        "success": True,
        "message": "Password reset successfully. Please log in again.",
    }


@router.get("/me", response_model=UserResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.get("/admin-check")
def admin_check(
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    return {
        "success": True,
        "message": "Admin access granted",
        "user_id": current_user.id,
        "role": current_user.role.value,
    }


@router.post("/refresh", response_model=TokenResponse)
def refresh_access_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    invalid_token = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or revoked refresh token",
    )

    try:
        payload = decode_token(request.refresh_token)

        if payload.get("type") != "refresh":
            raise invalid_token

        user_id = int(payload["sub"])
        token_hash = hash_refresh_token(request.refresh_token)

    except (InvalidTokenError, KeyError, TypeError, ValueError):
        raise invalid_token

    stored_token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .first()
    )

    now = _now_utc()

    if stored_token is None or stored_token.revoked_at is not None:
        raise invalid_token

    if (
        _as_utc(stored_token.expires_at) <= now
        or stored_token.user_id != user_id
    ):
        raise invalid_token

    user = db.query(User).filter(User.id == user_id).first()

    if user is None or not user.is_active:
        raise invalid_token

    stored_token.revoked_at = now.replace(tzinfo=None)

    try:
        result = issue_tokens(db, user)
    except Exception:
        db.rollback()
        raise

    return result


@router.post("/logout")
def logout_user(
    http_request: Request,
    request: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    try:
        payload = decode_token(request.refresh_token)

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        token_hash = hash_refresh_token(request.refresh_token)

    except (InvalidTokenError, KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    stored_token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .first()
    )

    if stored_token is None or stored_token.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or already revoked",
        )

    stored_token.revoked_at = _now_utc().replace(tzinfo=None)
    db.commit()

    _record_auth_audit_safely(
        db=db,
        request=http_request,
        event_type=AuditEventType.LOGOUT,
        action="LOGOUT",
        actor_id=stored_token.user_id,
        description="User logged out successfully.",
    )

    return {
        "success": True,
        "message": "Refresh token revoked successfully",
    }
