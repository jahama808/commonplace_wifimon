"""DB-backed dashboard repo — replaces `mock_dashboard.build_dashboard`
once the polling worker has written rows.

Wire shape (`schemas.dashboard.DashboardResponse`) is identical to the mock,
so the FastAPI endpoint and the frontend don't have to know which path
served the request.

Untested against a live Postgres in this conversion repo (we don't have
one wired up). Each query is documented with the source-of-truth model.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.common_area import CommonArea, Island
from app.models.connected_device_count import ConnectedDeviceCount
from app.models.network_status import NetworkStatus
from app.models.property import Property
from app.schemas.dashboard import (
    AlertItem,
    DashboardResponse,
    DeviceCountSeries,
    DeviceCountsResponse,
    HeatCallout,
    IslandSummary,
    MaintenanceWindow,
    PropertyPin,
)
from app.services.dashboard_aggregation import (
    ISLAND_LABEL,
    derive_pin,
    island_slug,
    status_rollup,
)
from app.services.maintenance import (
    get_affected_properties,
    list_active_future_maintenance,
)
from app.services.mock_dashboard import color_for_network

HST = ZoneInfo("Pacific/Honolulu")


async def build_dashboard_db(
    session: AsyncSession,
    *,
    island_filter: str | None = None,
    days: int = 7,
    ssid: str | None = None,
) -> DashboardResponse:
    now_utc = datetime.now(tz=UTC)

    properties_q = (
        select(Property)
        .options(
            selectinload(Property.common_areas),
            # `_central_office` reads `p.olt_cllis[0]` synchronously; without
            # eager loading SQLAlchemy emits a sync lazy-load mid-request and
            # asyncpg raises MissingGreenlet.
            selectinload(Property.olt_cllis),
        )
        .order_by(Property.name)
    )
    properties = (await session.execute(properties_q)).scalars().all()

    pins: list[PropertyPin] = []
    for p in properties:
        slug, status, offline = _property_status(p)
        if island_filter and island_filter != "all" and slug != island_filter:
            continue
        lng, lat = derive_pin(p.id, slug)
        pins.append(
            PropertyPin(
                id=str(p.id),
                name=p.name,
                island=slug,  # type: ignore[arg-type]
                central_office=_central_office(p),
                networks=len(p.common_areas),
                devices=await _latest_total_devices(session, p),
                status=status,
                offline_count=offline,
                lat=lat,
                lng=lng,
                spark=await _property_sparkline(session, p),
            )
        )

    islands = await _island_summaries(session, properties)
    hero = await _hero_chart(session, days=days, ssid=ssid)
    heatmap, peak, quiet = await _heatmap(session)
    alerts = await _recent_alerts(session, since=now_utc - timedelta(hours=24))
    available_ssids = await _available_ssids(session, since=now_utc - timedelta(days=days))
    maintenance = await _maintenance_windows(session)

    total_props = sum(i.properties for i in islands)
    total_nets = sum(i.networks for i in islands)
    total_devices = sum(p.devices for p in pins)
    outage_count = sum(1 for p in pins if p.status == "offline")
    degraded_count = sum(1 for p in pins if p.status == "degraded")
    online_count = sum(1 for p in pins if p.status == "online")

    return DashboardResponse(
        generated_at=now_utc.isoformat(),
        hst_now=now_utc.astimezone(HST).strftime("%H:%M:%S"),
        total_properties=total_props,
        total_networks=total_nets,
        total_devices=total_devices,
        avg_latency_ms=await _avg_latency_ms(session),
        outage_count=outage_count,
        degraded_count=degraded_count,
        online_count=online_count,
        islands=islands,
        properties=pins,
        alerts=alerts,
        hero_chart=hero,
        heatmap=heatmap,
        heatmap_peak=peak,
        heatmap_quiet=quiet,
        available_ssids=available_ssids,
        maintenance=maintenance,
    )


async def _maintenance_windows(session: AsyncSession) -> list[MaintenanceWindow]:
    """Active future maintenance + computed affected properties (SPEC §5.4)."""
    rows = await list_active_future_maintenance(session)
    out: list[MaintenanceWindow] = []
    for m in rows:
        affected = await get_affected_properties(session, m)
        out.append(
            MaintenanceWindow(
                id=m.id,
                island=m.island.value,
                scheduled=m.scheduled.astimezone(UTC).isoformat(),
                olt_clli_codes=[c.clli_code for c in m.olt_cllis],
                seven_fifty_clli_codes=[c.clli_code for c in m.seven_fifty_cllis],
                affected_property_names=[p.name for p in affected],
            )
        )
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _property_status(p: Property) -> tuple[str, str, int]:
    if not p.common_areas:
        return "oahu", "online", 0
    # Pick island = the most-common island across this property's areas, with
    # a fallback to the first.
    counts: dict[Island | None, int] = {}
    for ca in p.common_areas:
        counts[ca.island] = counts.get(ca.island, 0) + 1
    primary_island = max(counts, key=counts.get)
    slug = island_slug(primary_island)
    status, offline = status_rollup(
        [ca.is_online for ca in p.common_areas],
        [ca.is_chronic for ca in p.common_areas],
    )
    return slug, status, offline


def _central_office(p: Property) -> str:
    """SPEC §4.1 — first 8 chars of the first OLT CLLI's `clli_code`, or "—"."""
    if p.olt_cllis:
        code = p.olt_cllis[0].clli_code
        return code[:8] if code else "—"
    return "—"


async def _latest_total_devices(session: AsyncSession, p: Property) -> int:
    """Sum of the latest ssid="" total per CommonArea."""
    if not p.common_areas:
        return 0
    area_ids = [ca.id for ca in p.common_areas]
    # For each area, pick the most-recent ssid="" row.
    row_q = (
        select(
            ConnectedDeviceCount.common_area_id,
            func.max(ConnectedDeviceCount.timestamp).label("ts"),
        )
        .where(
            ConnectedDeviceCount.common_area_id.in_(area_ids),
            ConnectedDeviceCount.ssid == "",
        )
        .group_by(ConnectedDeviceCount.common_area_id)
        .subquery()
    )
    join_q = (
        select(func.coalesce(func.sum(ConnectedDeviceCount.count), 0))
        .join(
            row_q,
            and_(
                ConnectedDeviceCount.common_area_id == row_q.c.common_area_id,
                ConnectedDeviceCount.timestamp == row_q.c.ts,
            ),
        )
        .where(ConnectedDeviceCount.ssid == "")
    )
    return int((await session.execute(join_q)).scalar_one() or 0)


async def _property_sparkline(session: AsyncSession, p: Property, hours: int = 24) -> list[int]:
    """24-point hourly totals across all common areas (ssid=""). Buckets by
    hour-of-day; missing hours are zeros so the spark stays the right length.
    """
    if not p.common_areas:
        return [0] * hours
    cutoff = datetime.now(tz=UTC) - timedelta(hours=hours)
    area_ids = [ca.id for ca in p.common_areas]
    q = (
        select(
            func.date_trunc("hour", ConnectedDeviceCount.timestamp).label("h"),
            func.coalesce(func.sum(ConnectedDeviceCount.count), 0).label("c"),
        )
        .where(
            ConnectedDeviceCount.common_area_id.in_(area_ids),
            ConnectedDeviceCount.ssid == "",
            ConnectedDeviceCount.timestamp >= cutoff,
        )
        .group_by("h")
        .order_by("h")
    )
    rows = (await session.execute(q)).all()
    if not rows:
        return [0] * hours
    by_hour = {r[0]: int(r[1]) for r in rows}
    end = datetime.now(tz=UTC).replace(minute=0, second=0, microsecond=0)
    return [by_hour.get(end - timedelta(hours=hours - 1 - i), 0) for i in range(hours)]


async def _island_summaries(
    session: AsyncSession, properties: list[Property]
) -> list[IslandSummary]:
    out: list[IslandSummary] = []
    by_slug: dict[str, list[Property]] = {}
    for p in properties:
        slug, _, _ = _property_status(p)
        by_slug.setdefault(slug, []).append(p)

    for slug, label in ISLAND_LABEL.items():
        rows = by_slug.get(slug, [])
        if not rows:
            continue
        offline = sum(_property_status(p)[2] for p in rows)
        per_prop_devices = [await _latest_total_devices(session, p) for p in rows]
        out.append(
            IslandSummary(
                island=slug,  # type: ignore[arg-type]
                label=label,
                properties=len(rows),
                networks=sum(len(p.common_areas) for p in rows),
                devices=sum(per_prop_devices),
                offline=offline,
                status="offline" if offline > 0 else "online",
            )
        )
    return out


async def _hero_chart(
    session: AsyncSession, days: int, ssid: str | None
) -> DeviceCountsResponse:
    """Top-N stacked area for the dashboard hero. Picks the eight networks
    with the most devices in the window so the legend stays readable.
    """
    cutoff = datetime.now(tz=UTC) - timedelta(days=days)
    ssid_pred = ConnectedDeviceCount.ssid == (ssid if ssid else "")

    # Top-N areas by max recent count
    top_q = (
        select(
            ConnectedDeviceCount.common_area_id,
            func.max(ConnectedDeviceCount.count).label("peak"),
        )
        .where(ConnectedDeviceCount.timestamp >= cutoff, ssid_pred)
        .group_by(ConnectedDeviceCount.common_area_id)
        .order_by(func.max(ConnectedDeviceCount.count).desc())
        .limit(8)
    )
    top = (await session.execute(top_q)).all()
    if not top:
        return DeviceCountsResponse(timestamps=[], series=[], ssid=ssid)
    top_ids = [r[0] for r in top]

    # Pull all sample rows for those areas in window
    rows_q = (
        select(
            ConnectedDeviceCount.common_area_id,
            ConnectedDeviceCount.timestamp,
            ConnectedDeviceCount.count,
        )
        .where(
            ConnectedDeviceCount.common_area_id.in_(top_ids),
            ConnectedDeviceCount.timestamp >= cutoff,
            ssid_pred,
        )
        .order_by(ConnectedDeviceCount.timestamp)
    )
    rows = (await session.execute(rows_q)).all()

    # Pivot into series-by-area; canonicalize timestamps as the unique sorted set
    timestamps = sorted({r[1] for r in rows})
    ts_index = {t: i for i, t in enumerate(timestamps)}

    by_area: dict[int, list[int]] = {aid: [0] * len(timestamps) for aid in top_ids}
    for area_id, ts, count in rows:
        by_area[area_id][ts_index[ts]] = int(count)

    # Look up area names
    area_q = select(CommonArea).where(CommonArea.id.in_(top_ids))
    areas = {a.id: a for a in (await session.execute(area_q)).scalars().all()}

    series = [
        DeviceCountSeries(
            network_id=areas[aid].network_id if aid in areas else str(aid),
            network_name=(areas[aid].network_name or areas[aid].location_name) if aid in areas else f"Area {aid}",
            color=color_for_network(areas[aid].network_id if aid in areas else str(aid)),
            data=by_area[aid],
        )
        for aid in top_ids
    ]
    return DeviceCountsResponse(
        timestamps=[t.astimezone(UTC).isoformat() for t in timestamps],
        series=series,
        ssid=ssid,
    )


async def _heatmap(
    session: AsyncSession,
) -> tuple[list[list[float]], HeatCallout, HeatCallout]:
    """7-row × 24-col activity heatmap from the last 7 days of ssid="" totals.

    Cell value = average count at that (day-of-week, hour) bucket. Postgres
    `EXTRACT(DOW)` returns 0=Sun..6=Sat; we shift to Monday-first.
    """
    cutoff = datetime.now(tz=UTC) - timedelta(days=7)
    q = (
        select(
            func.extract("dow", ConnectedDeviceCount.timestamp).label("dow"),
            func.extract("hour", ConnectedDeviceCount.timestamp).label("hour"),
            func.avg(ConnectedDeviceCount.count).label("c"),
        )
        .where(
            ConnectedDeviceCount.timestamp >= cutoff,
            ConnectedDeviceCount.ssid == "",
        )
        .group_by("dow", "hour")
    )
    rows = (await session.execute(q)).all()

    days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    grid: list[list[float]] = [[0.0] * 24 for _ in range(7)]

    peak_count = -1.0
    peak_pos: tuple[int, int] = (0, 0)
    quiet_count = 1e18
    quiet_pos: tuple[int, int] = (0, 0)

    for dow_raw, hour_raw, c_raw in rows:
        # Postgres dow: 0=Sun..6=Sat → shift so Monday=0
        d = (int(dow_raw) + 6) % 7
        h = int(hour_raw)
        c = float(c_raw or 0)
        grid[d][h] = c
        if c > peak_count:
            peak_count = c
            peak_pos = (d, h)
        if c < quiet_count and c > 0:
            quiet_count = c
            quiet_pos = (d, h)

    if peak_count < 0:
        peak = HeatCallout(day="MON", hour=0, count=0)
        quiet = HeatCallout(day="MON", hour=0, count=0)
    else:
        peak = HeatCallout(day=days[peak_pos[0]], hour=peak_pos[1], count=int(peak_count))
        quiet = HeatCallout(day=days[quiet_pos[0]], hour=quiet_pos[1], count=int(quiet_count))

    return grid, peak, quiet


async def _recent_alerts(session: AsyncSession, since: datetime) -> list[AlertItem]:
    """Last 24h of network outage transitions, newest first.

    Picks each `NetworkStatus` row where `is_online=false`, joins on the
    CommonArea+Property for display strings.
    """
    q = (
        select(NetworkStatus)
        .options(
            selectinload(NetworkStatus.common_area).selectinload(CommonArea.property)
        )
        .where(NetworkStatus.checked_at >= since, NetworkStatus.is_online.is_(False))
        .order_by(NetworkStatus.checked_at.desc())
        .limit(50)
    )
    rows = (await session.execute(q)).scalars().all()

    out: list[AlertItem] = []
    for r in rows:
        ca = r.common_area
        prop = ca.property if ca is not None else None
        sev = "critical" if (ca and ca.is_chronic) else "warning"
        ts_local = r.checked_at.astimezone(HST)
        out.append(
            AlertItem(
                id=f"ns-{r.id}",
                severity=sev,  # type: ignore[arg-type]
                time=ts_local.strftime("%-I:%M %p"),
                property=prop.name if prop else "—",
                network=ca.location_name if ca else "—",
                message=r.error_message or "Network reported offline",
            )
        )
    return out


async def _available_ssids(session: AsyncSession, since: datetime) -> list[str]:
    q = (
        select(distinct(ConnectedDeviceCount.ssid))
        .where(
            ConnectedDeviceCount.timestamp >= since,
            ConnectedDeviceCount.ssid != "",
        )
        .order_by(ConnectedDeviceCount.ssid)
    )
    return [s for (s,) in (await session.execute(q)).all() if s]


async def _avg_latency_ms(session: AsyncSession) -> int:
    """Recent average response time across successful checks."""
    cutoff = datetime.now(tz=UTC) - timedelta(hours=1)
    q = select(func.avg(NetworkStatus.response_time_ms)).where(
        NetworkStatus.checked_at >= cutoff,
        NetworkStatus.response_time_ms.is_not(None),
        NetworkStatus.is_online.is_(True),
    )
    val = (await session.execute(q)).scalar()
    return int(val) if val is not None else 0
