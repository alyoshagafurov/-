"""Конфигурация приложения. Значения читаются из переменных окружения / .env."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # .../service
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = DATA_DIR / "results"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Secrets / auth
    secret_key: str = "dev-secret-change-me"
    access_token_expire_hours: int = 24 * 7  # неделя

    # Database (по умолчанию — SQLite по абсолютному пути, не зависит от CWD)
    database_url: str = f"sqlite:///{DATA_DIR / 'app.db'}"

    # First admin (seed)
    admin_email: str = "admin@example.com"
    admin_password: str = "admin12345"

    # Parser
    parser_max_workers: int = 8
    parser_watermark_crop: int = 48
    parser_timeout: int = 30
    parser_proxies: str = ""  # comma-separated

    # New-user defaults
    default_free_limit: int = 3
    default_free_days: int = 7

    # Email (заявки на оплату). Если smtp_host пуст — письма не шлются,
    # заявки всё равно сохраняются в админке.
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    owner_email: str = ""  # куда слать уведомления о заявках

    @property
    def proxy_list(self) -> list[str]:
        return [p.strip() for p in self.parser_proxies.split(",") if p.strip()]

    @property
    def mail_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.owner_email)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# Каталоги для результатов создаём заранее
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
