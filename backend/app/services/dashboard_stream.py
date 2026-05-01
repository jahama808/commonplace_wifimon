"""Async generators that emit dashboard-stream events.

Two backends:

  • `mock_event_stream`: synthetic 30s ticks for dev mode.
  • `db_event_stream`: polls the most-recent `network_status.checked_at`,
    emits when it changes. Lightweight (one indexed `MAX(checked_at)`
    query per cycle) and works without LISTEN/NOTIFY plumbing.

Each stream interleaves heartbeats so HTTP proxies don't drop the
connection. The wire format is the standard SSE encoding (a `data:` line
followed by a blank line); FastAPI's `StreamingResponse` passes the bytes
through unmodified.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.network_status import NetworkStatus

# Cadences. Don't sleep too aggressively — these run for the lifetime of
# the SSE connection (often hours).
HEARTBEAT_INTERVAL = 15.0   # seconds; SPEC: prevent proxy timeout
POLL_INTERVAL = 5.0         # seconds; how often to check for new events
MOCK_TICK_INTERVAL = 30.0   # seconds; mock mode synthetic events


def _sse(event_type: str, payload: dict) -> str:
    """Format one SSE message. Newlines in `data:` payload aren't allowed,
    so we JSON-encode (which always emits a single line)."""
    return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"


async def _heartbeat() -> str:
    """Comment-only line that EventSource ignores but proxies count as
    activity. SSE-spec compliant — `:` prefix is a comment."""
    return ":heartbeat\n\n"


async def mock_event_stream() -> AsyncIterator[str]:
    """Synthetic 30s ticks plus 15s heartbeats. Used in `USE_MOCK_DATA` mode."""
    yield _sse(
        "hello",
        {"mode": "mock", "ts": datetime.now(tz=UTC).isoformat()},
    )

    next_tick = asyncio.get_event_loop().time() + MOCK_TICK_INTERVAL
    next_hb = asyncio.get_event_loop().time() + HEARTBEAT_INTERVAL

    while True:
        now = asyncio.get_event_loop().time()
        sleep_for = max(0.05, min(next_tick, next_hb) - now)
        await asyncio.sleep(sleep_for)
        now = asyncio.get_event_loop().time()

        if now >= next_hb:
            yield await _heartbeat()
            next_hb = now + HEARTBEAT_INTERVAL
        if now >= next_tick:
            yield _sse(
                "dashboard.invalidate",
                {
                    "ts": datetime.now(tz=UTC).isoformat(),
                    "reason": "mock-tick",
                },
            )
            next_tick = now + MOCK_TICK_INTERVAL


async def db_event_stream(session_factory) -> AsyncIterator[str]:
    """Poll `MAX(network_status.checked_at)` and emit when it changes.

    `session_factory` is an async-sessionmaker (we open a fresh session
    per cycle so we don't pin a connection from the pool).
    """
    last_seen: datetime | None = None
    yield _sse("hello", {"mode": "db", "ts": datetime.now(tz=UTC).isoformat()})

    last_hb = asyncio.get_event_loop().time()

    while True:
        try:
            async with session_factory() as session:
                session: AsyncSession
                latest = (
                    await session.execute(select(func.max(NetworkStatus.checked_at)))
                ).scalar_one_or_none()
        except Exception:
            # DB hiccup — keep the connection alive, retry next loop.
            latest = None

        if latest is not None and (last_seen is None or latest > last_seen):
            last_seen = latest
            yield _sse(
                "dashboard.invalidate",
                {"ts": latest.astimezone(UTC).isoformat()},
            )

        now = asyncio.get_event_loop().time()
        if now - last_hb >= HEARTBEAT_INTERVAL:
            yield await _heartbeat()
            last_hb = now

        await asyncio.sleep(POLL_INTERVAL)
