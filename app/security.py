"""Хеширование паролей (bcrypt) и JWT-токены (PyJWT)."""
from datetime import timedelta

import bcrypt
import jwt

from .config import settings
from .models import utcnow

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int, is_admin: bool) -> str:
    expire = utcnow() + timedelta(hours=settings.access_token_expire_hours)
    payload = {"sub": str(user_id), "adm": is_admin, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
