"""Регистрация, вход, выход. Токен кладём в httpOnly-cookie."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import COOKIE_NAME
from ..models import User, utcnow
from ..schemas import LoginIn, RegisterIn
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_cookie(response: Response, user: User) -> None:
    token = create_access_token(user.id, user.is_admin)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.access_token_expire_hours * 3600,
        path="/",
        # secure=True,  # включить в проде за HTTPS
    )


@router.post("/register")
def register(data: RegisterIn, response: Response, db: Session = Depends(get_db)):
    exists = db.scalar(select(User).where(User.email == data.email.lower()))
    if exists:
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже есть")

    user = User(
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        # Новому пользователю — бесплатный стартовый доступ
        limit_count=settings.default_free_limit,
        access_until=utcnow() + timedelta(days=settings.default_free_days),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    _set_cookie(response, user)
    return {"ok": True, "is_admin": user.is_admin}


@router.post("/login")
def login(data: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Неверный email или пароль")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Аккаунт заблокирован")

    _set_cookie(response, user)
    return {"ok": True, "is_admin": user.is_admin}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}
