"""Mock implementation for `GET /api/v1/areas/{id}` (SPEC §5.6).

Routing key is the area's `network_id` (e.g. `AKS-001`, `PRK-002`) so the
frontend's URLs are stable and human-readable. We map back to the parent
property by stripping the suffix.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.schemas.area_detail import (
    AreaDetailResponse,
    EeroUnitRow,
    StatusHistoryPoint,
)
from app.services.mock_dashboard import _PROPERTIES_RAW, _seeded_random
from app.services.mock_property_detail import _NETWORK_NAMES


def _split_network_id(network_id: str) -> tuple[str, int] | None:
    """Synthetic ids look like `AKS-001`. Returns `(property_id, index_1)`."""
    parts = network_id.rsplit("-", 1)
    if len(parts) != 2:
        return None
    prop_id = parts[0].lower()
    try:
        idx = int(parts[1])
    except ValueError:
        return None
    return prop_id, idx


def _gen_eero_units(seed: int, count: int) -> list[EeroUnitRow]:
    rnd = _seeded_random(seed)
    models = ["eero Pro 6E", "eero Outdoor 7", "eero 6+", "eero Pro 6"]
    firmwares = ["7.4.1-198", "7.4.1-198", "7.3.0-156", "7.4.0-180"]
    locations = ["Front", "Back", "North", "South", "East", "West", "Center"]
    out: list[EeroUnitRow] = []
    for i in range(count):
        online = rnd() > 0.08
        out.append(
            EeroUnitRow(
                serial=f"EERO-{seed:04d}-{i + 1:03d}",
                location=locations[int(rnd() * len(locations)) % len(locations)],
                location_type="indoor" if rnd() > 0.3 else "outdoor",
                model=models[int(rnd() * len(models)) % len(models)],
                firmware_version=firmwares[int(rnd() * len(firmwares)) % len(firmwares)],
                is_online=online,
                connected_count=int(rnd() * 18) + 2 if online else 0,
            )
        )
    return out


def _gen_status_history(seed: int, count: int = 50, mostly_online: bool = True) -> list[StatusHistoryPoint]:
    """50 most-recent checks at 15-min cadence ending now (SPEC §5.6)."""
    rnd = _seeded_random(seed)
    now = datetime.now(tz=UTC).replace(microsecond=0)
    out: list[StatusHistoryPoint] = []
    flap_threshold = 0.96 if mostly_online else 0.4
    for i in range(count):
        is_online = rnd() < flap_threshold
        # Online responses: ~10..40ms. Offline: None.
        rt = round(10 + rnd() * 30) if is_online else None
        out.append(
            StatusHistoryPoint(
                checked_at=(now - timedelta(minutes=15 * (count - 1 - i))).isoformat(),
                is_online=is_online,
                response_time_ms=rt,
            )
        )
    return out


def build_area_detail(network_id: str) -> AreaDetailResponse | None:
    parsed = _split_network_id(network_id)
    if parsed is None:
        return None
    prop_id, idx_1 = parsed
    raw = next((p for p in _PROPERTIES_RAW if p["id"] == prop_id), None)
    if raw is None or idx_1 < 1 or idx_1 > raw["networks"]:
        return None

    names = _NETWORK_NAMES.get(prop_id, [f"Network {i + 1}" for i in range(raw["networks"])])
    location_name = names[idx_1 - 1]

    # Status: Park Lane has all networks offline; Pakalana has its single area
    # offline; everyone else online.
    is_online = True
    n_status = "online"
    if raw["status"] == "offline" or raw["status"] == "degraded" and idx_1 == 1:
        is_online = False
        n_status = "offline"

    seed = (hash(network_id) & 0xFFFF) or 1
    units = _gen_eero_units(seed=seed, count=max(2, min(6, 1 + (idx_1 % 5))))
    history = _gen_status_history(seed=seed + 1, mostly_online=is_online)

    devices_total = sum(u.connected_count for u in units)

    last_check = datetime.fromisoformat(history[-1].checked_at)

    return AreaDetailResponse(
        id=network_id,
        network_id=network_id,
        location_name=location_name,
        network_name=f"{raw['name']} · {location_name}",
        ssid="Guest" if idx_1 == 1 else "Staff",
        wan_ip=f"203.0.113.{(seed % 250) + 1}",
        location_type="outdoor" if idx_1 % 3 == 0 else "indoor",
        description=None,
        is_online=is_online,
        status=n_status,  # type: ignore[arg-type]
        last_checked=last_check.isoformat(),
        property_id=prop_id,
        property_name=raw["name"],
        insight_url=f"https://insight.eero.com/networks/{network_id}",
        eero_units=units,
        connected_total=devices_total,
        status_history=history,
    )
