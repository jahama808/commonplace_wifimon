"""FastAPI app entry point."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.sessions import SessionMiddleware

from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.core.config import settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT])

    app = FastAPI(
        title="Common Area Monitor API",
        version="0.1.0",
        docs_url="/api/v1/docs",
        openapi_url="/api/v1/openapi.json",
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # Cookie-based sessions — signed by SECRET_KEY, HttpOnly, SameSite=Lax.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SECRET_KEY,
        session_cookie=settings.SESSION_COOKIE_NAME,
        max_age=settings.SESSION_LIFETIME_DAYS * 24 * 3600,
        same_site="lax",
        https_only=settings.SESSION_COOKIE_SECURE,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(health_router)
    if settings.METRICS_ENABLED:
        app.include_router(metrics_router)

    return app


app = create_app()
