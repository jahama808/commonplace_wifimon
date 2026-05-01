"""DB-backed device-counts query.

Implements the SPEC §3 critical contract for `GET /api/v1/properties/{id}/device-counts`:

  • `ssid` omitted → totals from canonical `ssid=""` rows
  • `ssid` present → filtered series (one stack per network at that SSID)
  • Same sample timestamps drive both views (SPEC §3.4)
  • One color per `network_id`, stable across the dashboard / drawer / PDF

The same query reuses `extract_device_list` semantics: `connected_device_counts`
already stores the bucketed counts (the polling worker did that work), so this
function is pure aggregation + pivot.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.common_area import CommonArea
from app.models.connected_device_count import ConnectedDeviceCount
from app.schemas.dashboard import DeviceCountSeries, DeviceCountsResponse
from app.services.mock_dashboard import color_for_network


async def device_counts_for_property(
    session: AsyncSession,
    property_id: int,
    *,
    days: int,
    ssid: str | None = None,
) -> DeviceCountsResponse:
    """SPEC §3 critical contract.

    Returns one stack per CommonArea owned by the property, over the
    last `days` days.
    """
    cutoff = datetime.now(tz=UTC) - timedelta(days=days)

    # Resolve the property's common areas. Empty result is fine.
    areas_q = select(CommonArea).where(CommonArea.property_id == property_id)
    areas = (await session.execute(areas_q)).scalars().all()
    if not areas:
        return DeviceCountsResponse(timestamps=[], series=[], ssid=ssid)

    area_ids = [a.id for a in areas]

    # Pull every sample row in window for those areas at the requested ssid.
    # ssid="" sentinel means totals (SPEC §4.1).
    ssid_pred = ConnectedDeviceCount.ssid == (ssid if ssid else "")

    rows_q = (
        select(
            ConnectedDeviceCount.common_area_id,
            ConnectedDeviceCount.timestamp,
            ConnectedDeviceCount.count,
        )
        .where(
            ConnectedDeviceCount.common_area_id.in_(area_ids),
            ConnectedDeviceCount.timestamp >= cutoff,
            ssid_pred,
        )
        .order_by(ConnectedDeviceCount.timestamp)
    )
    rows = (await session.execute(rows_q)).all()

    if not rows:
        # SPEC §3.2: empty-state — still return the wire shape so the FE
        # renders "No samples in window" instead of erroring.
        return DeviceCountsResponse(timestamps=[], series=[], ssid=ssid)

    # Pivot: timestamps × area-id grid. Same timestamps drive both views.
    timestamps = sorted({r[1] for r in rows})
    ts_index = {t: i for i, t in enumerate(timestamps)}
    by_area: dict[int, list[int]] = {aid: [0] * len(timestamps) for aid in area_ids}
    for area_id, ts, count in rows:
        by_area[area_id][ts_index[ts]] = int(count)

    # Build series in a deterministic area-id order so colors stay stable.
    series = [
        DeviceCountSeries(
            network_id=a.network_id,
            network_name=a.network_name or a.location_name,
            color=color_for_network(a.network_id),
            data=by_area[a.id],
        )
        for a in sorted(areas, key=lambda x: x.id)
    ]
    return DeviceCountsResponse(
        timestamps=[t.astimezone(UTC).isoformat() for t in timestamps],
        series=series,
        ssid=ssid,
    )


async def ssids_for_property(
    session: AsyncSession, property_id: int, *, days: int = 7
) -> list[str]:
    """SPEC §7 — distinct SSIDs seen for any of the property's common areas
    in the time window. Excludes the empty-string totals sentinel.
    """
    cutoff = datetime.now(tz=UTC) - timedelta(days=days)
    q = (
        select(distinct(ConnectedDeviceCount.ssid))
        .join(CommonArea, ConnectedDeviceCount.common_area_id == CommonArea.id)
        .where(
            CommonArea.property_id == property_id,
            ConnectedDeviceCount.timestamp >= cutoff,
            ConnectedDeviceCount.ssid != "",
        )
        .order_by(ConnectedDeviceCount.ssid)
    )
    return [s for (s,) in (await session.execute(q)).all() if s]
