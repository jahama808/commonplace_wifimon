"""Shared fixtures.

Integration tests are gated on `TEST_DATABASE_URL`. If unset, tests
marked `integration` skip with a clear reason; unit tests run as normal.

Locally:

    createdb wifimon_test
    TEST_DATABASE_URL=postgresql+asyncpg://you@localhost/wifimon_test pytest

In CI: the workflow provisions a Postgres service container.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: requires a real Postgres reachable via TEST_DATABASE_URL",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-skip integration tests when the DB env isn't set, with a clear reason."""
    if os.getenv("TEST_DATABASE_URL"):
        return
    skip = pytest.mark.skip(reason="set TEST_DATABASE_URL to run integration tests")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


# Async fixtures are session-scoped where it's safe (engine, schema setup) and
# function-scoped where isolation matters (sessions roll back per test).


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine():
    url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(url, echo=False, pool_pre_ping=True)

    # Wipe + create the schema once per session. We use create_all rather than
    # alembic so test runs are fast; alembic's compiled SQL is verified
    # separately by the CI "render" step.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(db_engine) -> AsyncIterator[AsyncSession]:
    """Per-test session that rolls back on exit so tests don't leak state."""
    sm = async_sessionmaker(db_engine, expire_on_commit=False)
    async with sm() as session:
        try:
            yield session
        finally:
            # Reset any data the test created/committed. This is heavier than
            # a transaction-level rollback but works regardless of whether the
            # test code committed mid-flight (which most service code does).
            await session.rollback()
            for table in reversed(Base.metadata.sorted_tables):
                await session.execute(table.delete())
            await session.commit()
