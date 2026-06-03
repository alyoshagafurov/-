"""Зависимости FastAPI: извлечение текущего пользователя из cookie/заголовка."""
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .security import decode_access_token

COOKIE_NAME = "access_token"


def _extract_token(request: Request) -> str | None:
    # 1) Cookie (веб-интерфейс)
    token = request.cookies.get(COOKIE_NAME)
    if token:
        return token
    # 2) Authorization: Bearer (на будущее — внешнее API)
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def get_current_user_optional(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    token = _extract_token(request)
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None
    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(
    user: User | None = Depends(get_current_user_optional),
) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
        )
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Доступ только для администратора"
        )
    return user
