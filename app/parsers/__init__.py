"""Реестр парсеров. Добавление нового источника (ЦИАН/Яндекс/Домклик) —
это новый класс-наследник BaseParser с декоратором @register."""
from .base import BaseParser, ParseError, ParseResult, get_parser_for, register
from . import avito  # noqa: F401  — регистрирует AvitoParser

__all__ = [
    "BaseParser",
    "ParseError",
    "ParseResult",
    "get_parser_for",
    "register",
]
