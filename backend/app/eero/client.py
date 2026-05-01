"""eero API client (SPEC §5.2 / Appendix B).

Server-side only — `EERO_API_TOKEN` never reaches the browser. 10s timeout,
connection pool capped to 20/10 per `httpx.Limits`.

Endpoints:
  GET {base}{network_id}              → network metadata + health
  GET {base}{network_id}/eeros        → array of eero units
  GET {base}{network_id}/devices      → array of client devices
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from app.core.config import settings

log = structlog.get_logger(__name__)


@dataclass
class EeroResponse:
    """One call's outcome — used by `check_all_networks` to write `network_status` rows."""

    payload: Any
    status_code: int
    response_time_ms: int
    error_message: str = ""

    @property
    def ok(self) -> bool:
        return self.status_code == 200 and self.error_message == ""


class EeroClient:
    """Thin wrapper around `httpx.AsyncClient`. Use as an async context manager.

    Each network's check is isolated in the caller (try/except around it) so one
    bad response can't crash the polling loop. This client itself never raises;
    failures come back as `EeroResponse` with `ok == False`.
    """

    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._token = token if token is not None else settings.EERO_API_TOKEN
        self._base = (base_url or settings.EERO_API_BASE_URL).rstrip("/") + "/"
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> EeroClient:
        self._client = httpx.AsyncClient(
            timeout=self._timeout,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            headers={
                "X-User-Token": self._token,
                "User-Agent": "WiFi-Monitor/1.0",
                "Accept": "application/json",
            },
        )
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _url(self, network_id: str, suffix: str = "") -> str:
        # Allow per-area override via the model's `api_endpoint`.
        # Caller passes a full URL when available; otherwise we build from base.
        if network_id.startswith(("http://", "https://")):
            base = network_id.rstrip("/")
        else:
            base = f"{self._base}{network_id}"
        return f"{base}{suffix}"

    async def _get(self, network_id: str, suffix: str = "") -> EeroResponse:
        if self._client is None:
            raise RuntimeError("EeroClient not entered (use `async with`)")
        url = self._url(network_id, suffix)
        started = time.monotonic()
        try:
            resp = await self._client.get(url)
            dt = int((time.monotonic() - started) * 1000)
            try:
                payload: Any = resp.json()
            except ValueError:
                payload = None
            err = "" if resp.is_success else f"HTTP {resp.status_code}"
            return EeroResponse(
                payload=payload,
                status_code=resp.status_code,
                response_time_ms=dt,
                error_message=err,
            )
        except httpx.HTTPError as e:
            dt = int((time.monotonic() - started) * 1000)
            log.warning("eero.request_error", url=url, error=str(e))
            return EeroResponse(
                payload=None,
                status_code=0,
                response_time_ms=dt,
                error_message=str(e),
            )

    async def get_network(self, network_id_or_url: str) -> EeroResponse:
        """`GET {base}{network_id}` — network metadata + health.

        Used by `check_all_networks`. Caller passes either a network_id or a
        full URL (the `CommonArea.api_endpoint` override).
        """
        return await self._get(network_id_or_url)

    async def get_eeros(self, network_id_or_url: str) -> EeroResponse:
        """`GET {base}{network_id}/eeros` — array of physical eero units."""
        return await self._get(network_id_or_url, "/eeros")

    async def get_devices(self, network_id_or_url: str) -> EeroResponse:
        """`GET {base}{network_id}/devices` — array of client devices.

        Filter `connected: true` and bucket by `ssid` to compute the
        ConnectedDeviceCount rows.
        """
        return await self._get(network_id_or_url, "/devices")


@asynccontextmanager
async def eero_client():
    """Convenience: `async with eero_client() as c: ...` so callers don't
    have to remember the token + settings plumbing."""
    async with EeroClient() as c:
        yield c
