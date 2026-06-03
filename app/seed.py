"""Первичное наполнение БД: администратор и тарифы по умолчанию."""
from datetime import timedelta

from sqlalchemy import select

from .config import settings
from .database import SessionLocal
from .models import Tariff, User, utcnow
from .security import hash_password

DEFAULT_TARIFFS = [
    {
        "name": "Старт",
        "price": 490,
        "limit_count": 50,
        "duration_days": 30,
        "description": "50 обработок объявлений в месяц",
        "sort_order": 1,
    },
    {
        "name": "Профи",
        "price": 1490,
        "limit_count": 300,
        "duration_days": 30,
        "description": "300 обработок объявлений в месяц",
        "sort_order": 2,
    },
    {
        "name": "Безлимит",
        "price": 3990,
        "limit_count": 0,
        "duration_days": 30,
        "description": "Без ограничений на количество обработок (30 дней)",
        "sort_order": 3,
    },
]


def seed() -> None:
    db = SessionLocal()
    try:
        admin = db.scalar(select(User).where(User.email == settings.admin_email.lower()))
        if not admin:
            admin = User(
                email=settings.admin_email.lower(),
                password_hash=hash_password(settings.admin_password),
                is_admin=True,
                limit_count=0,  # безлимит
                access_until=utcnow() + timedelta(days=3650),
            )
            db.add(admin)
            db.commit()

        if not db.scalar(select(Tariff)):
            for data in DEFAULT_TARIFFS:
                db.add(Tariff(**data))
            db.commit()
    finally:
        db.close()
