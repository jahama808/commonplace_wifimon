"""Async orchestrator for property reports.

Gathers data from either the mock services or the DB, hands it to the sync
`pdf_report.build_pdf` via `run_in_executor` so the event loop stays free.
"""
from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.device_counts_db import (
    device_counts_for_property,
    ssids_for_property,
)
from app.services.mock_dashboard import AVAILABLE_SSIDS, _hero_chart
from app.services.mock_property_detail import build_property_detail
from app.services.pdf_report import (
    DeviceRow,
    ReportData,
    SsidChart,
    assign_chart_colors,
    build_pdf,
)
from app.services.property_detail_db import build_property_detail_db

HST = ZoneInfo("Pacific/Honolulu")


async def generate_property_report(
    session: AsyncSession,
    *,
    property_id: str,
    ssids: list[str],
) -> tuple[bytes, str]:
    """Returns `(pdf_bytes, filename)`.

    Empty `ssids` means "include all".
    """
    if settings.USE_MOCK_DATA:
        data = await _gather_mock(property_id, ssids)
    else:
        if not property_id.isdigit():
            raise ValueError("property not found")
        data = await _gather_db(session, int(property_id), ssids)

    pdf_bytes = await asyncio.get_running_loop().run_in_executor(None, build_pdf, data)
    filename = _filename(data.property_name, data.generated_at_hst)
    return pdf_bytes, filename


def _filename(property_name: str, when: datetime) -> str:
    # SPEC §5.7: `{property}_WiFi_Report_{YYYYMMDD_HHMMSS}.pdf`
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", property_name).strip("_") or "Property"
    return f"{slug}_WiFi_Report_{when.strftime('%Y%m%d_%H%M%S')}.pdf"


# ──────────────────────────────────────────────────────────────────────────────
# Mock-mode data gather
# ──────────────────────────────────────────────────────────────────────────────


async def _gather_mock(property_id: str, ssids: list[str]) -> ReportData:
    detail = build_property_detail(property_id)
    if detail is None:
        raise ValueError("property not found")

    selected = ssids if ssids else list(AVAILABLE_SSIDS)
    device_rows = [
        DeviceRow(
            location=d.name,
            model=d.model,
            connected_count=d.rssi if d.online else 0,
            status="online" if d.online else "offline",
        )
        for d in detail.devices
    ]

    network_names = [n.name for n in detail.networks]
    color_map = assign_chart_colors(network_names)

    ssid_charts: list[SsidChart] = []
    for ssid in selected:
        per_ssid = _hero_chart(days=1, ssid=ssid)
        ts = [datetime.fromisoformat(t).astimezone(HST) for t in per_ssid.timestamps]
        # Map mock series name → report-palette color
        series_by_name = {s.network_name: s.data for s in per_ssid.series}
        ssid_charts.append(
            SsidChart(
                ssid=ssid,
                timestamps=ts,
                series=series_by_name,
                colors={n: color_map.get(n, "#888888") for n in series_by_name},
            )
        )

    online = sum(1 for d in detail.devices if d.online)
    return ReportData(
        property_name=detail.name,
        generated_at_hst=datetime.now(tz=UTC).astimezone(HST),
        total_eeros=len(detail.devices),
        online_eeros=online,
        offline_eeros=len(detail.devices) - online,
        eero_models=_count_models([d.model for d in detail.devices]),
        devices=device_rows,
        ssid_charts=ssid_charts,
    )


def _count_models(models: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for m in models:
        out[m] = out.get(m, 0) + 1
    return out


# ──────────────────────────────────────────────────────────────────────────────
# DB-mode data gather
# ──────────────────────────────────────────────────────────────────────────────


async def _gather_db(
    session: AsyncSession, property_id: int, ssids: list[str]
) -> ReportData:
    detail = await build_property_detail_db(session, property_id)
    if detail is None:
        raise ValueError("property not found")

    if ssids:
        selected = ssids
    else:
        selected = await ssids_for_property(session, property_id, days=1)
    selected = selected or [""]  # at minimum, render the totals chart

    device_rows = [
        DeviceRow(
            location=d.name,
            model=d.model,
            connected_count=d.rssi if d.online else 0,
            status="online" if d.online else "offline",
        )
        for d in detail.devices
    ]

    network_names = [n.name for n in detail.networks]
    color_map = assign_chart_colors(network_names)

    ssid_charts: list[SsidChart] = []
    for ssid in selected:
        # ssid="" → totals
        payload = await device_counts_for_property(
            session, property_id, days=1, ssid=ssid or None
        )
        ts = [datetime.fromisoformat(t).astimezone(HST) for t in payload.timestamps]
        series_by_name = {s.network_name: s.data for s in payload.series}
        ssid_charts.append(
            SsidChart(
                ssid=ssid if ssid else "All SSIDs (totals)",
                timestamps=ts,
                series=series_by_name,
                colors={n: color_map.get(n, "#888888") for n in series_by_name},
            )
        )

    online = sum(1 for d in detail.devices if d.online)
    return ReportData(
        property_name=detail.name,
        generated_at_hst=datetime.now(tz=UTC).astimezone(HST),
        total_eeros=len(detail.devices),
        online_eeros=online,
        offline_eeros=len(detail.devices) - online,
        eero_models=_count_models([d.model for d in detail.devices]),
        devices=device_rows,
        ssid_charts=ssid_charts,
    )
