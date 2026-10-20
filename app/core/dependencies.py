
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.jwt import decode_token
from app.db.session import get_db
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing access token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_error

    try:
        payload = decode_token(credentials.credentials)

        if payload.get("type") != "access":
            raise credentials_error

        user_id = int(payload["sub"])

    except (InvalidTokenError, KeyError, TypeError, ValueError):
        raise credentials_error

    user = db.query(User).filter(User.id == user_id).first()

    if user is None or not user.is_active:
        raise credentials_error

    return user
