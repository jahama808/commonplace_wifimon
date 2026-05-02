"""DB-backed area detail repo. Mirrors `mock_area_detail.build_area_detail`
so the FE doesn't care which path served the request.

Lookup key is `network_id` (the human-routable identifier — same as in mock
mode and what the FE has in its URLs). The migrated DB preserves the
legacy eero network IDs (e.g. "20776644") in this column.
"""
from __future__ import annotations

from datetime import UTC

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.eero.client import eero_client
from app.eero.parser import device_eero_serial, extract_device_list
from app.models.common_area import CommonArea, LocationType
from app.models.connected_device_count import ConnectedDeviceCount
from app.models.network_status import NetworkStatus
from app.schemas.area_detail import (
    AreaDetailResponse,
    EeroUnitRow,
    StatusHistoryPoint,
)

log = structlog.get_logger(__name__)


async def build_area_detail_db(
    session: AsyncSession, network_id: str
) -> AreaDetailResponse | None:
    ca_q = (
        select(CommonArea)
        .options(
            selectinload(CommonArea.property),
            selectinload(CommonArea.eero_devices),
        )
        .where(CommonArea.network_id == network_id)
    )
    ca = (await session.execute(ca_q)).scalar_one_or_none()
    if ca is None:
        return None

    n_status = "online" if ca.is_online else ("offline" if ca.is_chronic else "degraded")

    history = await _status_history(session, ca.id, limit=50)

    # Per-eero connected counts aren't stored in our schema (the SPEC §5.6
    # computes them live from the eero `/devices` endpoint). Hit the API
    # at request time and bucket by source serial. If the call fails, we
    # fall back to per-eero=0 + the cached area total, which is a degraded
    # but non-broken view.
    per_eero, live_total = await _live_per_eero_counts(ca)
    units = [_eero_row(d, per_eero.get(d.serial, 0)) for d in ca.eero_devices]
    connected_total = (
        live_total if live_total is not None else await _latest_total(session, ca.id)
    )

    return AreaDetailResponse(
        id=ca.network_id,
        network_id=ca.network_id,
        location_name=ca.location_name,
        network_name=ca.network_name,
        ssid=ca.ssid,
        wan_ip=ca.wan_ip,
        location_type=ca.location_type.value,
        description=ca.description,
        is_online=ca.is_online,
        status=n_status,  # type: ignore[arg-type]
        last_checked=ca.last_checked.astimezone(UTC).isoformat() if ca.last_checked else None,
        property_id=str(ca.property_id),
        property_name=ca.property.name if ca.property else "—",
        insight_url=f"https://insight.eero.com/networks/{ca.network_id}",
        eero_units=units,
        connected_total=connected_total,
        status_history=history,
    )


def _eero_row(d, connected_count: int) -> EeroUnitRow:
    loc_type = (d.location_type or LocationType.INDOOR).value
    return EeroUnitRow(
        serial=d.serial,
        location=d.location,
        location_type=loc_type,  # type: ignore[arg-type]
        model=d.model,
        firmware_version=d.firmware_version,
        is_online=d.is_online,
        connected_count=connected_count,
    )


async def _live_per_eero_counts(ca: CommonArea) -> tuple[dict[str, int], int | None]:
    """Hit `/devices` for this network and bucket connected devices by their
    `source.serial_number`. Returns `(per_serial_count, total)` or `({}, None)`
    on any failure (missing token, unreachable, non-2xx, malformed payload).

    `total` reflects the same live snapshot, so when it's not None the
    per-eero rows always sum cleanly to the headline number.
    """
    if not settings.EERO_API_TOKEN:
        return {}, None
    target = ca.api_endpoint or ca.network_id
    try:
        async with eero_client() as c:
            resp = await c.get_devices(target)
    except Exception as e:
        log.warning("area.live_devices_failed", network_id=ca.network_id, error=str(e))
        return {}, None
    if not resp.ok or resp.payload is None:
        log.info(
            "area.live_devices_non_ok",
            network_id=ca.network_id,
            status=resp.status_code,
            error=resp.error_message,
        )
        return {}, None
    devices = extract_device_list(resp.payload)
    connected = [d for d in devices if d.get("connected") is True]
    counts: dict[str, int] = {}
    for d in connected:
        sn = device_eero_serial(d)
        if sn:
            counts[sn] = counts.get(sn, 0) + 1
    return counts, len(connected)


async def _latest_total(session: AsyncSession, area_id: int) -> int:
    q = (
        select(ConnectedDeviceCount.count)
        .where(
            ConnectedDeviceCount.common_area_id == area_id,
            ConnectedDeviceCount.ssid == "",
        )
        .order_by(ConnectedDeviceCount.timestamp.desc())
        .limit(1)
    )
    return int((await session.execute(q)).scalar() or 0)


async def _status_history(
    session: AsyncSession, area_id: int, limit: int
) -> list[StatusHistoryPoint]:
    """Most-recent N checks, returned chronological so the FE chart line
    runs left→right."""
    q = (
        select(NetworkStatus)
        .where(NetworkStatus.common_area_id == area_id)
        .order_by(NetworkStatus.checked_at.desc())
        .limit(limit)
    )
    rows = list((await session.execute(q)).scalars().all())
    rows.reverse()
    return [
        StatusHistoryPoint(
            checked_at=r.checked_at.astimezone(UTC).isoformat(),
            is_online=r.is_online,
            response_time_ms=r.response_time_ms,
        )
        for r in rows
    ]
