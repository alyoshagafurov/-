"""Парсер Avito.

ПРИНЦИП ЛАЗЕЙКИ (тот же, что у Юрия, актуализирован под Avito 2025+):
  Avito встраивает в HTML страницы данные объявления (SSR-гидрация). Среди них —
  массив `images` с числовыми ID фотографий. Оригиналы доступны на CDN по шаблону
  https://50.img.avito.st/1280x960/{id}.jpg — без авторизации и без защиты.
  Водяной знак «avito» — это нижняя полоса (~48px), она срезается через OpenCV.

  Извлечение ID — три стратегии (по очереди, для устойчивости к смене вёрстки):
    1) числовой массив `"images":[12345,...]` в SSR-данных (актуальный формат);
    2) window.__initialData__ (старый формат — как в исходном pars_link.py);
    3) хеш-ссылки media[].urls["1280x960"] без ?cqp= (запасной вариант).

Улучшения по сравнению с оригиналом клиента:
  * не привязан к конкретной версии ключа / структуры;
  * скачивание в несколько потоков (ThreadPoolExecutor);
  * поддержка ротации прокси;
  * обработка в отдельном каталоге задачи (без глобальных файлов — безопасно
    при множестве одновременных пользователей).
"""
from __future__ import annotations

import json
import os
import re
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import cycle
from urllib.parse import unquote

import cv2
import numpy as np
import requests
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from urllib3.util import ssl_

from ..config import settings
from .base import BaseParser, ParseError, ParseResult, register

# Набор шифров из оригинала — обходит блокировку Avito по TLS-fingerprint.
CIPHERS = (
    "ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES256-GCM-SHA384:"
    "ECDHE-RSA-AES256-SHA384:ECDHE-ECDSA-AES256-SHA384:"
    "ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-SHA256:AES256-SHA"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

CDN_TEMPLATE = "https://50.img.avito.st/1280x960/{id}.jpg"


class TlsAdapter(HTTPAdapter):
    def __init__(self, ssl_options: int = 0, **kwargs):
        self.ssl_options = ssl_options
        super().__init__(**kwargs)

    def init_poolmanager(self, *pool_args, **pool_kwargs):
        ctx = ssl_.create_urllib3_context(
            ciphers=CIPHERS, cert_reqs=ssl.CERT_REQUIRED, options=self.ssl_options
        )
        self.poolmanager = PoolManager(*pool_args, ssl_context=ctx, **pool_kwargs)


def _proxy_dict(proxy: str | None) -> dict | None:
    return {"http": proxy, "https": proxy} if proxy else None


def _resolution_score(url: str) -> int:
    m = re.search(r"/(\d+)x(\d+)/", url)
    return int(m.group(1)) * int(m.group(2)) if m else 0


@register
class AvitoParser(BaseParser):
    source = "avito"
    domains = ("avito.ru",)

    def __init__(
        self,
        max_workers: int | None = None,
        crop: int | None = None,
        timeout: int | None = None,
        proxies: list[str] | None = None,
    ):
        self.max_workers = max_workers or settings.parser_max_workers
        self.crop = settings.parser_watermark_crop if crop is None else crop
        self.timeout = timeout or settings.parser_timeout
        self.proxies = proxies if proxies is not None else settings.proxy_list
        self._proxy_cycle = cycle(self.proxies) if self.proxies else None

    def _next_proxy(self) -> str | None:
        return next(self._proxy_cycle) if self._proxy_cycle else None

    def _session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update(HEADERS)
        session.mount("https://", TlsAdapter(ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_3))
        return session

    # ── Получаем HTML страницы ──────────────────────────────
    def _fetch_page(self, url: str) -> str:
        session = self._session()
        try:
            resp = session.get(
                url, timeout=self.timeout, proxies=_proxy_dict(self._next_proxy())
            )
        except requests.RequestException as exc:
            raise ParseError(f"Не удалось открыть страницу объявления: {exc}") from exc
        return resp.text

    # ── Заголовок объявления ────────────────────────────────
    @staticmethod
    def _extract_title(text: str) -> str:
        for pat in (r'imageAlt\\":\\"([^\\]+)', r'"imageAlt"\s*:\s*"([^"]+)"'):
            m = re.search(pat, text)
            if m:
                return m.group(1).strip()
        m = re.search(r"<title>([^<]+)</title>", text)
        if m:
            return m.group(1).split(" - ")[0].strip()
        return ""

    # ── Стратегия 1: числовой массив images (актуальный) ───
    @staticmethod
    def _urls_from_numeric(text: str) -> list[str]:
        m = re.search(r'\\"images\\":\[(\d[\d,]*)\]', text)
        if not m:
            m = re.search(r'"images":\[(\d[\d,]*)\]', text)
        if not m:
            return []
        ids = [x for x in m.group(1).split(",") if x.strip().isdigit()]
        return [CDN_TEMPLATE.format(id=i) for i in ids]

    # ── Стратегия 2: window.__initialData__ (старый формат) ─
    @staticmethod
    def _urls_from_initial_data(text: str) -> list[str]:
        marker = "window.__initialData__ = "
        start = text.find(marker)
        if start == -1:
            return []
        rest = text[start:]
        raw = rest[: rest.find(";")].replace(marker, "")
        try:
            data = json.loads(unquote(raw).strip('"'))
        except (ValueError, json.JSONDecodeError):
            return []

        item = None
        for key, val in data.items():
            if key.startswith("@avito/bx-item-view") and isinstance(val, dict):
                item = val.get("buyerItem", {}).get("item")
                if isinstance(item, dict):
                    break
        if not item:
            return []

        urls: list[str] = []
        for el in item.get("images", []):
            if isinstance(el, (str, int)):
                urls.append(CDN_TEMPLATE.format(id=el))
            elif isinstance(el, dict):
                cdn = [v for v in el.values()
                       if isinstance(v, str) and "img.avito.st" in v]
                if cdn:
                    urls.append(max(cdn, key=_resolution_score))
                elif (ident := el.get("id") or el.get("hash")):
                    urls.append(CDN_TEMPLATE.format(id=ident))
        return urls

    # ── Стратегия 3: хеш-ссылки media (запасная) ───────────
    @staticmethod
    def _urls_from_hash(text: str) -> list[str]:
        pos = text.find('"media\\":')
        if pos == -1:
            pos = text.find('"media":')
        if pos == -1:
            return []
        chunk = text[pos: pos + 80_000]
        nxt = chunk.find('"media\\":', 20)
        if nxt == -1:
            nxt = chunk.find('"media":', 20)
        if nxt != -1:
            chunk = chunk[:nxt]

        raw = re.findall(r'1280x960\\":\\"(https://[^\\]+)', chunk)
        if not raw:
            raw = re.findall(r'"1280x960"\s*:\s*"(https://[^"]+)"', chunk)

        urls, seen = [], set()
        for u in raw:
            if "?cqp=" in u:  # с водяным знаком, пропускаем
                continue
            h = re.search(r"/1\.([A-Za-z0-9_\-]+)\.", u)
            key = h.group(1) if h else u
            if key not in seen:
                seen.add(key)
                urls.append(u)
        return urls

    # ── Скачать одно фото и срезать водяной знак ───────────
    def _fetch_clean(self, idx: int, url: str, out_dir: str) -> str | None:
        session = self._session()
        try:
            resp = session.get(
                url, timeout=self.timeout, proxies=_proxy_dict(self._next_proxy())
            )
            resp.raise_for_status()
        except requests.RequestException:
            return None

        img = cv2.imdecode(np.frombuffer(resp.content, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return None
        if self.crop > 0 and img.shape[0] > self.crop:
            img = img[: -self.crop, :]  # срезаем водяной знак снизу

        out_path = os.path.join(out_dir, f"{idx:03d}.jpg")
        if not cv2.imwrite(out_path, img):
            return None
        return out_path

    # ── Публичный метод ─────────────────────────────────────
    def parse(self, url: str, out_dir: str) -> ParseResult:
        text = self._fetch_page(url)
        title = self._extract_title(text)

        photo_urls = (
            self._urls_from_numeric(text)
            or self._urls_from_initial_data(text)
            or self._urls_from_hash(text)
        )
        if not photo_urls:
            raise ParseError(
                "Не нашёл фотографии объявления на странице. "
                "Возможно, ссылка неверная, объявление снято или Avito изменил структуру."
            )

        os.makedirs(out_dir, exist_ok=True)
        results: list[str] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = [
                pool.submit(self._fetch_clean, i, u, out_dir)
                for i, u in enumerate(photo_urls, start=1)
            ]
            for fut in as_completed(futures):
                if (path := fut.result()):
                    results.append(path)

        if not results:
            raise ParseError(
                "Не удалось скачать ни одной фотографии. "
                "Попробуйте позже или включите прокси."
            )

        results.sort()
        return ParseResult(title=title, image_paths=results)
