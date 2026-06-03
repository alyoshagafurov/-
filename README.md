# ФотоЧист — сервис очистки фотографий недвижимости

Аналог antiznak.ru: пользователь вставляет ссылку на объявление Avito → получает
архив с очищенными фотографиями. Есть регистрация, тарифы/лимиты, личный кабинет
и админка. Парсер переработан под веб: многопоточность, поддержка прокси,
безопасная обработка при множестве одновременных пользователей.

## Стек
- **Backend:** FastAPI (Python 3.12)
- **Frontend:** Jinja2-шаблоны + ванильный JS (без сборки, минимализм)
- **БД:** SQLAlchemy — SQLite по умолчанию, PostgreSQL в проде (через `DATABASE_URL`)
- **Обработка изображений:** OpenCV + Pillow
- **Авторизация:** JWT в httpOnly-cookie, пароли — bcrypt

## Быстрый старт (локально)

```bash
cd service
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # отредактируйте SECRET_KEY, ADMIN_*
uvicorn app.main:app --reload
```

Откройте http://127.0.0.1:8000

- Главная — обработка по ссылке
- `/register` — регистрация (стартовый бесплатный лимит задаётся в `.env`)
- `/admin` — вход под администратором из `.env` (`ADMIN_EMAIL` / `ADMIN_PASSWORD`)

## Запуск в Docker (с PostgreSQL)

```bash
cd service
SECRET_KEY=$(python -c "import secrets;print(secrets.token_hex(32))") \
ADMIN_PASSWORD=your-strong-pass \
docker compose up --build
```

## Структура

```
app/
  main.py            точка входа FastAPI
  config.py          настройки из .env
  database.py        SQLAlchemy (SQLite/PostgreSQL)
  models.py          User, Tariff, Job, Comment
  schemas.py         Pydantic-схемы
  security.py        bcrypt + JWT
  deps.py            авторизация (cookie/Bearer)
  seed.py            первый админ + тарифы по умолчанию
  parsers/
    base.py          базовый класс + реестр источников
    avito.py         парсер Avito (многопоточность + прокси)
  services/
    processing.py    оркестрация задачи: парсинг → zip → статус
  routers/
    pages.py         HTML-страницы
    auth.py          регистрация/вход/выход
    jobs.py          создать обработку / статус / скачать
    admin.py         пользователи, тарифы, лимиты, комментарии
    public.py        список тарифов, профиль
  templates/  static/
```

## Как работает парсер (принцип «лазейки»)

Avito кладёт данные объявления в HTML-переменную `window.__initialData__` (JSON).
Внутри — массив `images` с идентификаторами фотографий. Оригиналы доступны на CDN
по шаблону `https://50.img.avito.st/1280x960/{id}.jpg`. Водяной знак — это нижняя
полоса, она срезается (по умолчанию 48 px, настраивается `PARSER_WATERMARK_CROP`).

Отличия от исходного скрипта клиента:
- поиск ключа `@avito/bx-item-view:*` **динамический** (исходник был привязан к
  версиям `3.133.1` / `3.144.2` и ломался при обновлении Avito);
- скачивание фото в несколько потоков (`PARSER_MAX_WORKERS`);
- **ротация прокси** (`PARSER_PROXIES`);
- обработка в отдельном временном каталоге задачи, **без глобальных файлов** —
  безопасно при множестве одновременных пользователей;
- устойчивость к разной форме поля `images`.

### Добавление нового источника (ЦИАН / Яндекс / Домклик)
Создать класс-наследник `BaseParser` в `app/parsers/`, реализовать `parse()` и
повесить декоратор `@register` с доменами. Реестр сам подберёт парсер по ссылке.

## Переменные окружения
См. `.env.example`. Ключевые:
- `SECRET_KEY` — обязательно сменить в проде.
- `DATABASE_URL` — SQLite или PostgreSQL.
- `PARSER_MAX_WORKERS`, `PARSER_PROXIES`, `PARSER_WATERMARK_CROP`, `PARSER_TIMEOUT`.
- `ADMIN_EMAIL` / `ADMIN_PASSWORD` — первый администратор.
- `DEFAULT_FREE_LIMIT` / `DEFAULT_FREE_DAYS` — стартовый доступ новым пользователям.

## Заметки для прода
- Включить `secure=True` для cookie в `app/routers/auth.py` (за HTTPS).
- Сменить `SECRET_KEY` и пароль администратора.
- Обработка задач сейчас на `BackgroundTasks` (в пуле потоков). Под высокую
  нагрузку вынести в Celery + Redis — архитектура парсера это уже позволяет.
- Платёжная система и Telegram-бот — следующий этап (модели тарифов готовы).
```
