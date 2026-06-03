"""Настройка SQLAlchemy. Поддерживает SQLite (по умолчанию) и PostgreSQL."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

# Для SQLite нужен флаг check_same_thread=False, т.к. обработка идёт в фоновом потоке
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI-зависимость: отдаёт сессию и закрывает её после запроса."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Создаёт таблицы. Модели импортируются ради регистрации в метаданных."""
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
