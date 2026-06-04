"""ORM-модели: пользователи, тарифы, задачи обработки, комментарии админа."""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Tariff(Base):
    """Шаблон тарифа. Админ назначает его пользователю — это задаёт лимит и срок."""

    __tablename__ = "tariffs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    price: Mapped[int] = mapped_column(Integer, default=0)  # рубли
    limit_count: Mapped[int] = mapped_column(Integer, default=0)  # 0 = безлимит
    duration_days: Mapped[int] = mapped_column(Integer, default=30)
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    users: Mapped[list["User"]] = relationship(back_populates="tariff")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Доступ: лимит обработок и срок. Заполняется при назначении тарифа,
    # но админ может переопределить вручную.
    tariff_id: Mapped[int | None] = mapped_column(ForeignKey("tariffs.id"), nullable=True)
    limit_count: Mapped[int] = mapped_column(Integer, default=0)  # 0 = безлимит
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    access_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    tariff: Mapped["Tariff | None"] = relationship(back_populates="users")
    jobs: Mapped[list["Job"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    # ── Помощники доступа ──────────────────────────────────
    @property
    def access_active(self) -> bool:
        if self.access_until is None:
            return False
        until = self.access_until
        if until.tzinfo is None:  # SQLite возвращает naive datetime
            until = until.replace(tzinfo=timezone.utc)
        return until > utcnow()

    @property
    def remaining(self) -> int | None:
        """Сколько обработок осталось. None = безлимит."""
        if self.limit_count == 0:
            return None
        return max(self.limit_count - self.used_count, 0)

    @property
    def can_process(self) -> bool:
        if self.is_admin:
            return True
        if not self.access_active:
            return False
        rem = self.remaining
        return rem is None or rem > 0


class Job(Base):
    """Одна задача обработки объявления."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source: Mapped[str] = mapped_column(String(40), default="avito")
    url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # pending | processing | done | error
    title: Mapped[str] = mapped_column(String(255), default="")
    photo_count: Mapped[int] = mapped_column(Integer, default=0)
    result_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="jobs")


class Comment(Base):
    """Комментарий админа к пользователю (для CRM-логики из ТЗ)."""

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    author: Mapped[str] = mapped_column(String(255), default="admin")
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="comments")


class PaymentRequest(Base):
    """Заявка на оплату тарифа (платёжка ещё не подключена — приходит в админку)."""

    __tablename__ = "payment_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    tariff_id: Mapped[int | None] = mapped_column(ForeignKey("tariffs.id"), nullable=True)
    tariff_name: Mapped[str] = mapped_column(String(120), default="")
    email: Mapped[str] = mapped_column(String(255), index=True)
    phone: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)  # new | done
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
