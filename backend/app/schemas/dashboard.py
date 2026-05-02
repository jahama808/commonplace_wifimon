"""Pydantic models that mirror the frontend `DashboardResponse` contract.

These are the wire shapes consumed by the Next.js dashboard. They match
`design_handoff_common_area_monitor_redesign/SPEC.md` §7 and the per-network
device-counts contract from §3 / README "Backend Contract".
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Status = Literal["online", "degraded", "offline"]
Island = Literal["oahu", "maui", "big-island", "kauai", "molokai", "lanai"]
Severity = Literal["critical", "warning", "info"]


class IslandSummary(BaseModel):
    island: Island
    label: str
    properties: int
    networks: int
    devices: int
    offline: int
    status: Status


class PropertyPin(BaseModel):
    id: str
    name: str
    island: Island
    central_office: str  # retained for the detail-page header; the list shows address
    address: str | None = None
    networks: int
    devices: int
    status: Status
    offline_count: int = 0
    lat: float = Field(..., description="0..1 normalized for the map SVG")
    lng: float = Field(..., description="0..1 normalized for the map SVG")
    spark: list[int] = Field(default_factory=list)


class AlertItem(BaseModel):
    id: str
    severity: Severity
    time: str
    property: str
    network: str
    device: str | None = None
    message: str
    acknowledged: bool = False


class DeviceCountSeries(BaseModel):
    network_id: str
    network_name: str
    color: str
    data: list[int]


class DeviceCountsResponse(BaseModel):
    """Contract for `GET /api/v1/properties/{id}/device-counts`.

    Same shape is embedded into the dashboard hero chart so the frontend can
    use a single component for both views.
    """
    timestamps: list[str]
    series: list[DeviceCountSeries]
    ssid: str | None = None


class HeatCallout(BaseModel):
    day: str
    hour: int
    count: int


class MaintenanceWindow(BaseModel):
    """Light-weight wire shape for the dashboard's "Scheduled Maintenance"
    card. Full admin shape lives in `schemas/maintenance.py`."""
    id: int
    island: str
    scheduled: str  # ISO timestamp
    olt_clli_codes: list[str] = Field(default_factory=list)
    seven_fifty_clli_codes: list[str] = Field(default_factory=list)
    affected_property_names: list[str] = Field(default_factory=list)


class DashboardResponse(BaseModel):
    generated_at: str
    hst_now: str

    total_properties: int
    total_networks: int
    total_devices: int
    avg_latency_ms: int

    outage_count: int
    degraded_count: int
    online_count: int

    islands: list[IslandSummary]
    properties: list[PropertyPin]
    alerts: list[AlertItem]
    hero_chart: DeviceCountsResponse
    heatmap: list[list[float]]
    heatmap_peak: HeatCallout
    heatmap_quiet: HeatCallout
    available_ssids: list[str] = Field(default_factory=list)
    maintenance: list[MaintenanceWindow] = Field(default_factory=list)
