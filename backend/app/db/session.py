"""Async engine + session factory.

The engine is created lazily so the FastAPI app can boot in mock mode
without a Postgres reachable.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _ensure_engine() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    global _engine, _sessionmaker
    if _engine is None or _sessionmaker is None:
        _engine = create_async_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=10,
        )
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine, _sessionmaker


def get_engine() -> AsyncEngine:
    return _ensure_engine()[0]


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: `Depends(get_session)`."""
    _, sm = _ensure_engine()
    async with sm() as session:
        yield session


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
