"""Pydantic-схемы для API (валидация ввода и сериализация ответов)."""
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ── Auth ───────────────────────────────────────────────────
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


# ── Jobs ───────────────────────────────────────────────────
class JobCreateIn(BaseModel):
    url: str = Field(min_length=5, max_length=2000)


class JobOut(BaseModel):
    id: int
    source: str
    url: str
    status: str
    title: str
    photo_count: int
    error: str
    created_at: datetime
    finished_at: datetime | None

    class Config:
        from_attributes = True


# ── Admin ──────────────────────────────────────────────────
class AssignTariffIn(BaseModel):
    tariff_id: int | None = None
    limit_count: int | None = None      # переопределить лимит вручную
    extra_days: int | None = None       # продлить доступ на N дней
    reset_used: bool = False            # обнулить счётчик использованных


class CommentIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class TariffIn(BaseModel):
    name: str
    price: int = 0
    limit_count: int = 0
    duration_days: int = 30
    description: str = ""
    is_active: bool = True
    sort_order: int = 0
