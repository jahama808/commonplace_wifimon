"""DB-backed property detail repo. Mirrors the wire shape of
`mock_property_detail.build_property_detail` so the FE doesn't care which
path served the request.

Untested against a live Postgres in this conversion repo.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.common_area import CommonArea
from app.models.connected_device_count import ConnectedDeviceCount
from app.models.network_status import NetworkStatus
from app.models.property import Property
from app.schemas.dashboard import DeviceCountSeries, DeviceCountsResponse
from app.schemas.property_detail import (
    DeviceRow,
    MduOltInfo,
    NetworkRow,
    PropertyDetailResponse,
)
from app.services.dashboard_aggregation import island_slug, status_rollup
from app.services.mdu_olt_map import lookup_by_property_name
from app.services.mock_dashboard import color_for_network


async def build_property_detail_db(
    session: AsyncSession, property_id: int | str
) -> PropertyDetailResponse | None:
    # Property IDs in the wire shape are strings (mock used "aks", "prk", …);
    # the DB uses int. Try both.
    p = await _load_property(session, property_id)
    if p is None:
        return None

    networks: list[NetworkRow] = []
    for ca in p.common_areas:
        latest = await _latest_total_for_area(session, ca.id)
        n_status = "online" if ca.is_online else ("offline" if ca.is_chronic else "degraded")
        networks.append(
            NetworkRow(
                network_id=ca.network_id,
                name=ca.network_name or ca.location_name,
                status=n_status,  # type: ignore[arg-type]
                devices=latest,
                color=color_for_network(ca.network_id),
            )
        )

    devices: list[DeviceRow] = []
    for ca in p.common_areas:
        for d in ca.eero_devices:
            devices.append(
                DeviceRow(
                    name=f"{d.location or ca.location_name} · {d.serial[-4:] if d.serial else '----'}",
                    mac=d.serial or "—",
                    model=d.model or "eero",
                    rssi=5 if d.is_online else 0,  # eero API doesn't expose RSSI per unit; placeholder
                    online=d.is_online,
                )
            )

    chart = await _mini_chart(session, [ca.id for ca in p.common_areas])
    rollup_status, _offline = status_rollup(
        [ca.is_online for ca in p.common_areas],
        [ca.is_chronic for ca in p.common_areas],
    )
    # Prefer the property's own island; fall back to the most-common
    # common-area island for un-migrated rows.
    primary_island = p.island or (p.common_areas[0].island if p.common_areas else None)

    # Aggregate eero model + firmware across every unit on the property —
    # feeds the two side panels on the property detail page (SPEC §5.5).
    eero_models: dict[str, int] = {}
    firmware_versions: dict[str, int] = {}
    for ca in p.common_areas:
        for d in ca.eero_devices:
            model_key = d.model or "Unknown"
            eero_models[model_key] = eero_models.get(model_key, 0) + 1
            fw_key = d.firmware_version or "Unknown"
            firmware_versions[fw_key] = firmware_versions.get(fw_key, 0) + 1

    mdu_match = await lookup_by_property_name(session, p.name)
    mdu_olt = (
        MduOltInfo(
            mdu_name=mdu_match.mdu_name,
            fdh_name=mdu_match.fdh_name,
            olt_clli=mdu_match.equip_name,
            olt_type=mdu_match.serving_olt,
            seven_fifty=mdu_match.equip_name_1,
            seven_fifty_model=mdu_match.equip_model,
        )
        if mdu_match
        else None
    )

    return PropertyDetailResponse(
        id=str(p.id),
        name=p.name,
        island=island_slug(primary_island),  # type: ignore[arg-type]
        central_office=_first_co(p),
        status=rollup_status,
        networks_count=len(p.common_areas),
        devices_count=sum(n.devices for n in networks),
        uptime_pct=await _uptime_pct(session, p, hours=24 * 7),
        chart=chart,
        networks=networks,
        devices=devices,
        eero_models=eero_models,
        firmware_versions=firmware_versions,
        mdu_olt=mdu_olt,
    )


async def _load_property(session: AsyncSession, property_id: int | str) -> Property | None:
    q = select(Property).options(
        selectinload(Property.common_areas).selectinload(CommonArea.eero_devices),
        selectinload(Property.olt_cllis),
    )
    if isinstance(property_id, int) or (isinstance(property_id, str) and property_id.isdigit()):
        q = q.where(Property.id == int(property_id))
    else:
        # Fallback: lookup by name slug (last-ditch convenience for human ids).
        q = q.where(Property.name == property_id)
    return (await session.execute(q)).scalar_one_or_none()


def _first_co(p: Property) -> str:
    if p.olt_cllis:
        code = p.olt_cllis[0].clli_code
        return code[:8] if code else "—"
    return "—"


async def _latest_total_for_area(session: AsyncSession, area_id: int) -> int:
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


async def _mini_chart(
    session: AsyncSession, area_ids: list[int], hours: int = 24
) -> DeviceCountsResponse:
    if not area_ids:
        return DeviceCountsResponse(timestamps=[], series=[], ssid=None)

    cutoff = datetime.now(tz=UTC) - timedelta(hours=hours)
    rows_q = (
        select(
            ConnectedDeviceCount.common_area_id,
            ConnectedDeviceCount.timestamp,
            ConnectedDeviceCount.count,
        )
        .where(
            ConnectedDeviceCount.common_area_id.in_(area_ids),
            ConnectedDeviceCount.ssid == "",
            ConnectedDeviceCount.timestamp >= cutoff,
        )
        .order_by(ConnectedDeviceCount.timestamp)
    )
    rows = (await session.execute(rows_q)).all()
    if not rows:
        return DeviceCountsResponse(timestamps=[], series=[], ssid=None)

    timestamps = sorted({r[1] for r in rows})
    ts_index = {t: i for i, t in enumerate(timestamps)}
    by_area: dict[int, list[int]] = {aid: [0] * len(timestamps) for aid in area_ids}
    for area_id, ts, count in rows:
        by_area[area_id][ts_index[ts]] = int(count)

    area_q = select(CommonArea).where(CommonArea.id.in_(area_ids))
    areas = {a.id: a for a in (await session.execute(area_q)).scalars().all()}
    series = [
        DeviceCountSeries(
            network_id=areas[aid].network_id,
            network_name=areas[aid].network_name or areas[aid].location_name,
            color=color_for_network(areas[aid].network_id),
            data=by_area[aid],
        )
        for aid in area_ids
        if aid in areas
    ]
    return DeviceCountsResponse(
        timestamps=[t.astimezone(UTC).isoformat() for t in timestamps],
        series=series,
        ssid=None,
    )


async def _uptime_pct(session: AsyncSession, p: Property, hours: int = 168) -> float:
    """Fraction of `network_status` rows that were online over the window."""
    if not p.common_areas:
        return 100.0
    cutoff = datetime.now(tz=UTC) - timedelta(hours=hours)
    area_ids = [ca.id for ca in p.common_areas]
    q = select(
        func.count().filter(NetworkStatus.is_online.is_(True)),
        func.count(),
    ).where(
        NetworkStatus.common_area_id.in_(area_ids),
        NetworkStatus.checked_at >= cutoff,
    )
    online_count, total = (await session.execute(q)).one()
    if not total:
        return 100.0
    return round(100.0 * online_count / total, 2)
