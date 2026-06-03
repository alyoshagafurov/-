"""Публичные/пользовательские эндпоинты: список тарифов и профиль."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Tariff, User

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/tariffs")
def list_tariffs(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Tariff)
        .where(Tariff.is_active == True)  # noqa: E712
        .order_by(Tariff.sort_order, Tariff.price)
    ).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "price": t.price,
            "limit_count": t.limit_count,
            "duration_days": t.duration_days,
            "description": t.description,
        }
        for t in rows
    ]


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "is_admin": user.is_admin,
        "tariff": user.tariff.name if user.tariff else None,
        "limit_count": user.limit_count,
        "used_count": user.used_count,
        "remaining": user.remaining,
        "access_until": user.access_until.isoformat() if user.access_until else None,
        "access_active": user.access_active,
        "can_process": user.can_process,
    }
