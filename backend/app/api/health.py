"""`/health` endpoint (SPEC §6.3).

Returns `{db: ok|fail|skipped, eero: configured|missing, last_poll: <iso>|null}`
with the right HTTP status: 200 if everything's healthy, 503 if the DB is
unreachable.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Response, status
from sqlalchemy import func, select

from app.core.config import settings
from app.db.session import _ensure_engine

router = APIRouter()


@router.get("/health")
async def health(response: Response) -> dict[str, Any]:
    db_status = "skipped"  # mock mode
    last_poll: str | None = None

    if not settings.USE_MOCK_DATA:
        try:
            from app.models.network_status import NetworkStatus

            _, sm = _ensure_engine()
            async with sm() as session:
                # Cheap ping
                await session.execute(select(1))
                # Latest sample timestamp — proxy for "is the worker alive?"
                latest = (
                    await session.execute(select(func.max(NetworkStatus.checked_at)))
                ).scalar_one_or_none()
                if latest is not None:
                    last_poll = latest.astimezone(UTC).isoformat()
            db_status = "ok"
        except Exception as e:  # noqa: BLE001
            db_status = "fail"
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {
                "db": db_status,
                "eero": _eero_status(),
                "last_poll": None,
                "error": str(e),
            }

    return {
        "db": db_status,
        "eero": _eero_status(),
        "last_poll": last_poll,
        "now": datetime.now(tz=UTC).isoformat(),
    }


def _eero_status() -> str:
    return "configured" if settings.EERO_API_TOKEN else "missing"
