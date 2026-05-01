"""Notifier interface (SPEC §5.3).

Default impl is `PushoverNotifier`. Alternatives (Slack, email, Twilio SMS)
can be added later without touching the polling code. Selection at startup
via `get_notifier()` based on env config.

Per SPEC §5.3 trigger rules:
  • network_offline   — title "NETWORK OFFLINE",   sound updown,  priority 1, suppress if chronic (>1h)
  • network_recovered — title "NETWORK RECOVERED", sound magic,   priority 0, always send on transition
  • device_offline    — title "EERO DEVICE OFFLINE",   sound falling, priority 1, suppress chronic (>24h), else max 1/day
  • device_recovered  — title "EERO DEVICE RECOVERED", sound magic,   priority 0, always send on transition

Each `send_*` method returns the wire-level body that was sent (or would have
been sent for the Null impl) so callers can assert on it in tests.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import httpx
import structlog

from app.core.config import settings

if TYPE_CHECKING:
    from app.models.common_area import CommonArea
    from app.models.eero_device import EeroDevice

log = structlog.get_logger(__name__)


@dataclass
class NotificationPayload:
    title: str
    message: str
    priority: int
    sound: str


class Notifier(ABC):
    @abstractmethod
    async def send_network_offline(self, area: CommonArea) -> NotificationPayload: ...

    @abstractmethod
    async def send_network_recovered(self, area: CommonArea) -> NotificationPayload: ...

    @abstractmethod
    async def send_device_offline(
        self, device: EeroDevice, area: CommonArea
    ) -> NotificationPayload: ...

    @abstractmethod
    async def send_device_recovered(
        self, device: EeroDevice, area: CommonArea
    ) -> NotificationPayload: ...


class _PropertyAccessor(Protocol):
    @property
    def name(self) -> str: ...


def _network_message(area: CommonArea) -> str:
    prop_name = area.property.name if area.property is not None else "(unknown property)"
    return f"{prop_name} · {area.location_name}"


def _device_message(device: EeroDevice, area: CommonArea) -> str:
    prop_name = area.property.name if area.property is not None else "(unknown property)"
    bits = [
        f"{prop_name} · {area.location_name}",
        f"{device.model or 'eero'} ({device.location_type.value})",
    ]
    if device.location:
        bits.append(device.location)
    return " · ".join(bits)


def _build_payload(kind: str, area: CommonArea, device: EeroDevice | None = None) -> NotificationPayload:
    if kind == "network_offline":
        return NotificationPayload("NETWORK OFFLINE", _network_message(area), 1, "updown")
    if kind == "network_recovered":
        return NotificationPayload("NETWORK RECOVERED", _network_message(area), 0, "magic")
    if kind == "device_offline":
        assert device is not None
        return NotificationPayload("EERO DEVICE OFFLINE", _device_message(device, area), 1, "falling")
    if kind == "device_recovered":
        assert device is not None
        return NotificationPayload("EERO DEVICE RECOVERED", _device_message(device, area), 0, "magic")
    raise ValueError(f"unknown notification kind: {kind}")


class NullNotifier(Notifier):
    """Logs-only notifier — used in dev / when Pushover isn't configured."""

    async def _emit(self, kind: str, payload: NotificationPayload) -> NotificationPayload:
        log.info("notify.skipped", kind=kind, title=payload.title, message=payload.message)
        return payload

    async def send_network_offline(self, area):
        return await self._emit("network_offline", _build_payload("network_offline", area))

    async def send_network_recovered(self, area):
        return await self._emit("network_recovered", _build_payload("network_recovered", area))

    async def send_device_offline(self, device, area):
        return await self._emit("device_offline", _build_payload("device_offline", area, device))

    async def send_device_recovered(self, device, area):
        return await self._emit("device_recovered", _build_payload("device_recovered", area, device))


class PushoverNotifier(Notifier):
    """HTTPS POST to Pushover (SPEC §5.3)."""

    URL = "https://api.pushover.net/1/messages.json"

    def __init__(self, app_token: str, user_key: str) -> None:
        self.app_token = app_token
        self.user_key = user_key

    async def _post(self, payload: NotificationPayload) -> NotificationPayload:
        body = {
            "token": self.app_token,
            "user": self.user_key,
            "title": payload.title,
            "message": payload.message,
            "priority": payload.priority,
            "sound": payload.sound,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                resp = await c.post(self.URL, data=body)
                if not resp.is_success:
                    log.warning("pushover.error", status=resp.status_code, body=resp.text)
        except httpx.HTTPError as e:
            log.warning("pushover.request_error", error=str(e))
        return payload

    async def send_network_offline(self, area):
        return await self._post(_build_payload("network_offline", area))

    async def send_network_recovered(self, area):
        return await self._post(_build_payload("network_recovered", area))

    async def send_device_offline(self, device, area):
        return await self._post(_build_payload("device_offline", area, device))

    async def send_device_recovered(self, device, area):
        return await self._post(_build_payload("device_recovered", area, device))


def get_notifier() -> Notifier:
    """Pick `PushoverNotifier` if configured, else `NullNotifier`."""
    if settings.PUSHOVER_APP_TOKEN and settings.PUSHOVER_USER_KEY:
        return PushoverNotifier(settings.PUSHOVER_APP_TOKEN, settings.PUSHOVER_USER_KEY)
    return NullNotifier()
