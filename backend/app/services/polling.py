"""Polling jobs (SPEC §5.2).

Four jobs the worker schedules. Each is callable from APScheduler **and** from
the `wifimon check --force` CLI / admin "force check" endpoint.

Critical invariants:
  • One bad response can't crash the loop — every per-network call is wrapped.
  • Each `record_device_counts` tick writes EXACTLY one ssid="" total row PLUS
    one row per distinct SSID per network. The chart layer depends on this.
  • 7-day GC for `connected_device_counts` (configurable via env later).
  • Network chronic = offline for >1h, device chronic = offline for >24h.
  • Pushover throttle: device "offline" max 1/day; "recovered" always sends.
    Network "offline" suppressed once chronic; "recovered" always sends.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.eero.client import EeroClient, EeroResponse
from app.eero.parser import (
    bucket_connected_by_ssid,
    determine_online,
    extract_device_list,
    extract_network_metadata,
)
from app.models.common_area import CommonArea
from app.models.connected_device_count import ConnectedDeviceCount
from app.models.eero_device import EeroDevice
from app.models.network_status import NetworkStatus
from app.services.notifier import Notifier, get_notifier

log = structlog.get_logger(__name__)

NETWORK_CHRONIC_AFTER = timedelta(hours=1)
DEVICE_CHRONIC_AFTER = timedelta(hours=24)
DEVICE_NOTIFICATION_THROTTLE = timedelta(hours=24)
DEVICE_COUNT_RETENTION = timedelta(days=7)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _endpoint_for(area: CommonArea) -> str:
    """SPEC §4.1 — `api_endpoint` overrides the default `{base}{network_id}`."""
    return area.api_endpoint or area.network_id


# ──────────────────────────────────────────────────────────────────────────────
# 1) check_all_networks — every 15 min
# ──────────────────────────────────────────────────────────────────────────────


async def check_all_networks(
    session: AsyncSession,
    *,
    client: EeroClient,
    notifier: Notifier | None = None,
    force: bool = False,
) -> int:
    """Iterate over every CommonArea, hit `GET {base}{network_id}`, update
    cached state, write a `network_status` row, fire transition notifications.

    Returns the number of networks checked. Per-network 1-hour rate limit
    (`area.can_check_status()`) unless `force=True`.
    """
    notifier = notifier or get_notifier()
    now = _now()

    rows = (
        await session.execute(
            select(CommonArea).options(selectinload(CommonArea.property))
        )
    ).scalars().all()

    checked = 0
    for area in rows:
        if not force and not area.can_check_status(now=now):
            continue
        try:
            resp = await client.get_network(_endpoint_for(area))
            await _apply_network_check(session, area, resp, notifier=notifier, now=now)
            checked += 1
        except Exception as e:  # noqa: BLE001 — isolation is the whole point
            log.exception("polling.network_check_failed", area_id=area.id, error=str(e))

    await session.commit()
    return checked


async def _apply_network_check(
    session: AsyncSession,
    area: CommonArea,
    resp: EeroResponse,
    *,
    notifier: Notifier,
    now: datetime,
) -> None:
    is_online = resp.ok and determine_online(resp.payload)

    # Append-only history row (SPEC §4.1)
    session.add(
        NetworkStatus(
            common_area_id=area.id,
            is_online=is_online,
            checked_at=now,
            response_time_ms=resp.response_time_ms,
            error_message=resp.error_message,
            raw_response=resp.payload if isinstance(resp.payload, dict) else None,
        )
    )

    prev_online = area.is_online
    prev_chronic = area.is_chronic

    # Refresh metadata when we got a usable payload
    if resp.ok:
        meta = extract_network_metadata(resp.payload)
        if "network_name" in meta:
            area.network_name = meta["network_name"]
        if "ssid" in meta:
            area.ssid = meta["ssid"]
        if "wan_ip" in meta:
            area.wan_ip = meta["wan_ip"]

    # State transitions
    if is_online:
        if not prev_online:
            await notifier.send_network_recovered(area)
        area.is_online = True
        area.offline_since = None
        area.is_chronic = False
    else:
        if prev_online:
            # First-time offline — start the chronic clock
            area.offline_since = now
            area.is_chronic = False
            await notifier.send_network_offline(area)
        else:
            # Was already offline; check chronic transition
            became_chronic = (
                area.offline_since is not None
                and now - area.offline_since >= NETWORK_CHRONIC_AFTER
            )
            if became_chronic and not prev_chronic:
                area.is_chronic = True  # suppress further "offline" notifications
        area.is_online = False

    area.last_checked = now


# ──────────────────────────────────────────────────────────────────────────────
# 2) check_all_devices — every 15 min
# ──────────────────────────────────────────────────────────────────────────────


async def check_all_devices(
    session: AsyncSession,
    *,
    client: EeroClient,
    notifier: Notifier | None = None,
) -> int:
    notifier = notifier or get_notifier()
    now = _now()

    rows = (
        await session.execute(
            select(CommonArea).options(
                selectinload(CommonArea.property),
                selectinload(CommonArea.eero_devices),
            )
        )
    ).scalars().all()

    networks = 0
    for area in rows:
        try:
            resp = await client.get_eeros(_endpoint_for(area))
            await _apply_device_check(session, area, resp, notifier=notifier, now=now)
            networks += 1
        except Exception as e:  # noqa: BLE001
            log.exception("polling.device_check_failed", area_id=area.id, error=str(e))

    await session.commit()
    return networks


async def _apply_device_check(
    session: AsyncSession,
    area: CommonArea,
    resp: EeroResponse,
    *,
    notifier: Notifier,
    now: datetime,
) -> None:
    if not resp.ok:
        return  # Don't churn DB state on a bad fetch.

    raw = extract_device_list(resp.payload)
    seen_serials: set[str] = set()

    by_serial = {d.serial: d for d in area.eero_devices}

    for unit in raw:
        serial = unit.get("serial_number") or unit.get("serial")
        if not isinstance(serial, str) or not serial:
            continue
        seen_serials.add(serial)

        existing = by_serial.get(serial)
        unit_online = bool(unit.get("online", unit.get("status") == "green"))
        if existing is None:
            existing = EeroDevice(
                common_area_id=area.id,
                serial=serial,
                model=unit.get("model"),
                location=unit.get("location"),
                firmware_version=unit.get("os_version") or unit.get("firmware_version"),
                is_online=unit_online,
                offline_since=None if unit_online else now,
            )
            session.add(existing)
            area.eero_devices.append(existing)
        else:
            existing.model = unit.get("model") or existing.model
            existing.location = unit.get("location") or existing.location
            fw = unit.get("os_version") or unit.get("firmware_version")
            if fw:
                existing.firmware_version = fw

        await _apply_device_transition(existing, unit_online, area=area, notifier=notifier, now=now)

    # Delete devices that vanished from the response (SPEC §5.2)
    for d in list(area.eero_devices):
        if d.serial not in seen_serials and d.id is not None:
            await session.delete(d)


async def _apply_device_transition(
    device: EeroDevice,
    is_online: bool,
    *,
    area: CommonArea,
    notifier: Notifier,
    now: datetime,
) -> None:
    prev_online = device.is_online
    prev_chronic = device.is_chronic

    if is_online:
        if not prev_online:
            await notifier.send_device_recovered(device, area)
        device.is_online = True
        device.offline_since = None
        device.is_chronic = False
        return

    # offline branch
    if prev_online:
        device.offline_since = now
        device.is_chronic = False
        await notifier.send_device_offline(device, area)
        device.last_notification_sent = now
    else:
        became_chronic = (
            device.offline_since is not None
            and now - device.offline_since >= DEVICE_CHRONIC_AFTER
        )
        if became_chronic and not prev_chronic:
            device.is_chronic = True
        elif not device.is_chronic:
            # Not yet chronic — re-notify at most once per throttle window.
            last = device.last_notification_sent
            if last is None or now - last >= DEVICE_NOTIFICATION_THROTTLE:
                await notifier.send_device_offline(device, area)
                device.last_notification_sent = now
    device.is_online = False


# ──────────────────────────────────────────────────────────────────────────────
# 3) record_device_counts ⭐ — every 15 min day, every 30 min night (SPEC §3)
# ──────────────────────────────────────────────────────────────────────────────


async def record_device_counts(
    session: AsyncSession,
    *,
    client: EeroClient,
) -> int:
    """For every common area, write ONE total row (ssid="") + N per-SSID rows.
    Then GC anything older than `DEVICE_COUNT_RETENTION`.
    """
    now = _now()

    rows = (await session.execute(select(CommonArea))).scalars().all()

    written = 0
    for area in rows:
        try:
            resp = await client.get_devices(_endpoint_for(area))
            if not resp.ok:
                continue
            devices = extract_device_list(resp.payload)
            total, per_ssid = bucket_connected_by_ssid(devices)

            # Canonical "total" row — empty-string SSID sentinel (SPEC §4.1).
            session.add(
                ConnectedDeviceCount(
                    common_area_id=area.id, count=total, ssid="", timestamp=now
                )
            )
            written += 1
            for ssid, count in per_ssid.items():
                session.add(
                    ConnectedDeviceCount(
                        common_area_id=area.id, count=count, ssid=ssid, timestamp=now
                    )
                )
                written += 1
        except Exception as e:  # noqa: BLE001
            log.exception("polling.device_counts_failed", area_id=area.id, error=str(e))

    # 7-day GC
    cutoff = now - DEVICE_COUNT_RETENTION
    await session.execute(
        delete(ConnectedDeviceCount).where(ConnectedDeviceCount.timestamp < cutoff)
    )

    await session.commit()
    return written


# ──────────────────────────────────────────────────────────────────────────────
# 4) update_firmware_versions — daily 03:00 HST (just re-runs device check)
# ──────────────────────────────────────────────────────────────────────────────


async def update_firmware_versions(session: AsyncSession, *, client: EeroClient) -> int:
    """SPEC §5.2 — daily refresh of firmware strings via the same /eeros call.

    Doesn't fire notifications (device transitions are owned by the 15-min job).
    """
    now = _now()
    rows = (
        await session.execute(
            select(CommonArea).options(selectinload(CommonArea.eero_devices))
        )
    ).scalars().all()

    updated = 0
    for area in rows:
        try:
            resp = await client.get_eeros(_endpoint_for(area))
            if not resp.ok:
                continue
            for unit in extract_device_list(resp.payload):
                serial = unit.get("serial_number") or unit.get("serial")
                fw = unit.get("os_version") or unit.get("firmware_version")
                if not (isinstance(serial, str) and isinstance(fw, str)):
                    continue
                for existing in area.eero_devices:
                    if existing.serial == serial:
                        if existing.firmware_version != fw:
                            existing.firmware_version = fw
                            existing.last_updated = now
                            updated += 1
                        break
        except Exception as e:  # noqa: BLE001
            log.exception("polling.firmware_check_failed", area_id=area.id, error=str(e))

    await session.commit()
    return updated


# ──────────────────────────────────────────────────────────────────────────────
# 5) force_check_area — on-demand single-network refresh (SPEC §5.2)
# ──────────────────────────────────────────────────────────────────────────────


async def force_check_area(
    session: AsyncSession,
    area: CommonArea,
    *,
    client: EeroClient,
    notifier: Notifier | None = None,
) -> tuple[bool, datetime]:
    """Run all three eero calls (network / eeros / devices) for one area now,
    bypassing the per-network 1-hour rate limit. Used by the admin "Force
    check now" button and by `wifimon check --force --area=…`.

    Returns `(is_online, checked_at)` reflecting the post-call state.

    The caller is expected to have eager-loaded `area.eero_devices` if it
    wants device-row updates to skip an extra round-trip; we tolerate
    either since the lazy load happens inside this same async session.
    """
    notifier = notifier or get_notifier()
    now = _now()
    area_id = area.id  # capture before any session.refresh that could expire
    target = _endpoint_for(area)

    # Eager-load the relationships the downstream code touches synchronously
    # (notifier reads `area.property.name`; _apply_device_check dedupes on
    # `area.eero_devices`). Without this, a transition fires lazy SQL inside
    # the async context and asyncpg raises MissingGreenlet.
    await session.refresh(area, attribute_names=["property", "eero_devices"])

    # 1) /network → updates is_online + writes a NetworkStatus row
    try:
        net_resp = await client.get_network(target)
        await _apply_network_check(session, area, net_resp, notifier=notifier, now=now)
    except Exception as e:  # noqa: BLE001
        log.exception("polling.force_network_failed", area_id=area_id, error=str(e))

    # 2) /eeros → upserts EeroDevice rows + transitions
    try:
        eeros_resp = await client.get_eeros(target)
        await _apply_device_check(session, area, eeros_resp, notifier=notifier, now=now)
    except Exception as e:  # noqa: BLE001
        log.exception("polling.force_eeros_failed", area_id=area_id, error=str(e))

    # 3) /devices → writes ConnectedDeviceCount rows (one ssid="" total + per-SSID)
    try:
        dev_resp = await client.get_devices(target)
        if dev_resp.ok:
            devices = extract_device_list(dev_resp.payload)
            total, per_ssid = bucket_connected_by_ssid(devices)
            session.add(
                ConnectedDeviceCount(
                    common_area_id=area_id, count=total, ssid="", timestamp=now
                )
            )
            for ssid, count in per_ssid.items():
                session.add(
                    ConnectedDeviceCount(
                        common_area_id=area_id, count=count, ssid=ssid, timestamp=now
                    )
                )
    except Exception as e:  # noqa: BLE001
        log.exception("polling.force_devices_failed", area_id=area_id, error=str(e))

    await session.commit()
    return area.is_online, area.last_checked or now
