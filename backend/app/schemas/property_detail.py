"""Wire shapes for `GET /api/v1/properties/{id}` — drives the dashboard drawer
AND the standalone property detail page (SPEC §5.5)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.dashboard import DeviceCountsResponse, Status


class NetworkRow(BaseModel):
    network_id: str
    name: str
    status: Status
    devices: int  # latest connected count
    color: str   # stable color-by-network_id
    location_type: Literal["indoor", "outdoor"] | None = None
    description: str | None = None
    last_checked: str | None = None  # ISO timestamp


class DeviceRow(BaseModel):
    name: str
    mac: str
    model: str
    rssi: int  # 0..5 segments
    online: bool
    firmware_version: str | None = None
    location_type: Literal["indoor", "outdoor"] | None = None


class MduOltInfo(BaseModel):
    """Populated when the property's name matches an entry in the uploaded
    MDU↔OLT map (admin → MDU Map upload)."""

    mdu_name: str
    fdh_name: str | None = None
    olt_clli: str | None = None  # equip_name in the source spreadsheet
    olt_type: str | None = None  # serving_olt
    seven_fifty: str | None = None  # equip_name_1
    seven_fifty_model: str | None = None  # equip_model


class PropertyDetailResponse(BaseModel):
    id: str
    name: str
    island: Literal["oahu", "maui", "big-island", "kauai", "molokai", "lanai"]
    central_office: str
    status: Status
    address: str | None = None
    created_at: str | None = None  # ISO timestamp

    networks_count: int
    devices_count: int
    uptime_pct: float  # 0..100, last 7d

    # Aggregates for the detail-page side panels (SPEC §5.5)
    eero_models: dict[str, int] = Field(default_factory=dict)
    firmware_versions: dict[str, int] = Field(default_factory=dict)

    chart: DeviceCountsResponse  # 24h mini
    networks: list[NetworkRow]
    devices: list[DeviceRow]

    mdu_olt: MduOltInfo | None = None
