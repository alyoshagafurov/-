"""Базовый интерфейс парсера и реестр источников.

Каждый источник (avito, cian, yandex, domclik …) — отдельный класс-наследник
BaseParser. Принцип одинаковый: достать ID/ссылки оригинальных фото из данных
страницы, скачать в несколько потоков (с прокси) и убрать водяной знак.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse


class ParseError(Exception):
    """Понятная пользователю ошибка парсинга."""


@dataclass
class ParseResult:
    title: str
    image_paths: list[str] = field(default_factory=list)


# domain-substring -> parser class
_REGISTRY: dict[str, type["BaseParser"]] = {}


def register(cls: type["BaseParser"]) -> type["BaseParser"]:
    for domain in cls.domains:
        _REGISTRY[domain] = cls
    return cls


def get_parser_for(url: str) -> "BaseParser":
    host = (urlparse(url).hostname or "").lower()
    if not host:
        raise ParseError("Не похоже на ссылку. Вставьте полный адрес объявления.")
    for domain, cls in _REGISTRY.items():
        if domain in host:
            return cls()
    supported = ", ".join(sorted({d for d in _REGISTRY}))
    raise ParseError(f"Этот сайт пока не поддерживается. Доступно: {supported}")


class BaseParser:
    source: str = "base"
    domains: tuple[str, ...] = ()

    def parse(self, url: str, out_dir: str) -> ParseResult:
        """Скачать и очистить фото объявления в каталог out_dir."""
        raise NotImplementedError
