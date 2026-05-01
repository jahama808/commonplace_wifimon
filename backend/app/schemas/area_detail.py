"""Wire shapes for `GET /api/v1/areas/{id}` (SPEC §5.6)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.dashboard import Status


class EeroUnitRow(BaseModel):
    serial: str
    location: str | None = None
    location_type: Literal["indoor", "outdoor"]
    model: str | None = None
    firmware_version: str | None = None
    is_online: bool
    # Per-eero connected device count — computed live from /devices by counting
    # where device.source.serial_number == eero.serial (SPEC §5.6).
    connected_count: int = 0


class StatusHistoryPoint(BaseModel):
    checked_at: str  # ISO timestamp
    is_online: bool
    response_time_ms: int | None = None


class AreaDetailResponse(BaseModel):
    id: str  # network_id (the human-routable identifier)
    network_id: str
    location_name: str
    network_name: str | None = None
    ssid: str | None = None
    wan_ip: str | None = None
    location_type: Literal["indoor", "outdoor"]
    description: str | None = None
    is_online: bool
    status: Status
    last_checked: str | None = None  # ISO timestamp

    # Parent property — for the back link + sticky header
    property_id: str
    property_name: str

    # Eero Insight deep-link target: https://insight.eero.com/networks/{network_id}
    insight_url: str

    eero_units: list[EeroUnitRow]
    connected_total: int
    status_history: list[StatusHistoryPoint]
