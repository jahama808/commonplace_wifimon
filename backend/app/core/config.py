"""Typed configuration via environment variables."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve `.env` against the repo root rather than the current working
# directory, so `cd backend && alembic upgrade head` (and any other ad-hoc
# CLI invocation) reads the same .env the systemd units inject. Path:
# this file is at backend/app/core/config.py, so the repo root is 3 up.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore"
    )

    # Required in real envs; defaults exist so the app boots in dev.
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/wifimon"
    SECRET_KEY: str = "dev-secret-not-for-prod"

    # eero
    EERO_API_TOKEN: str = ""
    EERO_API_BASE_URL: str = "https://api-user.e2ro.com/2.2/networks/"

    # Pushover
    PUSHOVER_APP_TOKEN: str = ""
    PUSHOVER_USER_KEY: str = ""

    # Frontend / CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # Local dev convenience: serve mock dashboard data instead of querying the DB.
    USE_MOCK_DATA: bool = True

    # Auth
    SESSION_LIFETIME_DAYS: int = 14
    SESSION_COOKIE_NAME: str = "wifimon_session"
    # `true` in prod (HTTPS only). Override via env in deploy.
    SESSION_COOKIE_SECURE: bool = False

    # Rate limit (SPEC §5.1) — 30 req/min per IP, returns 429.
    RATE_LIMIT: str = "30/minute"

    # Observability (SPEC §6.3)
    LOG_FORMAT: str = "pretty"  # "pretty" for dev, "json" for prod
    LOG_LEVEL: str = "info"
    METRICS_ENABLED: bool = True


settings = Settings()
