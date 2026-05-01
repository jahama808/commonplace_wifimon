"""Deterministic mock for `GET /api/v1/properties/{id}`."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.schemas.dashboard import DeviceCountSeries, DeviceCountsResponse
from app.schemas.property_detail import DeviceRow, NetworkRow, PropertyDetailResponse
from app.services.mock_dashboard import _PROPERTIES_RAW, _seeded_random, color_for_network

HST = ZoneInfo("Pacific/Honolulu")

# Per-property network rosters. Keys mirror `_PROPERTIES_RAW[*].id`. The list
# length matches `networks` from the dashboard fixture; status comes from the
# property's roll-up status (so "Park Lane" shows offline networks).
_NETWORK_NAMES: dict[str, list[str]] = {
    "aks": ["Lobby / Front Desk", "Pool / Bar"],
    "bvk": ["Lobby", "Pool Deck", "Spa", "Gym"],
    "cap": ["Lobby", "Conference Rm 1", "Conference Rm 2"],
    "hbr": ["Guest WiFi"],
    "imp": ["Lobby"],
    "kol": ["Lobby", "Pool"],
    "khl": ["Operations"],
    "owk": ["Common Area"],
    "prk": [
        "Lobby/Front Desk", "Parking Garage / BBQ Area", "Pool Deck", "Gym",
        "Spa", "Cabana 1", "Cabana 2", "Cabana 3", "Conference",
        "Tennis Pro Shop", "Maintenance LAN", "Loading Dock", "Roof Deck",
    ],
    "pak": ["Pool Deck"],
    "mok": ["Lobby", "Garden"],
    "kon": ["Lobby", "Pool", "Beach Bar"],
    "wai": ["Lobby", "Pool"],
    "lhi": ["Front Desk"],
    "pri": ["Lobby", "Pool"],
}


def _gen_devices(seed: int, count: int) -> list[DeviceRow]:
    rnd = _seeded_random(seed)
    out: list[DeviceRow] = []
    models = ["eero Pro 6E", "eero Outdoor 7", "eero 6+", "eero Pro 6"]
    firmwares = ["7.4.1-198", "7.4.1-198", "7.3.0-156", "7.4.0-180"]  # weighted toward latest
    for i in range(count):
        mac = ":".join(f"{int(rnd() * 255):02X}" for _ in range(6))
        rssi = round(rnd() * 5)
        online = rnd() > 0.05
        out.append(
            DeviceRow(
                name=f"AP-{seed:02d}-{i + 1:02d}",
                mac=mac,
                model=models[int(rnd() * len(models)) % len(models)],
                firmware_version=firmwares[int(rnd() * len(firmwares)) % len(firmwares)],
                location_type="indoor" if rnd() > 0.3 else "outdoor",
                rssi=rssi if online else 0,
                online=online,
            )
        )
    return out


def _mini_chart(networks: list[NetworkRow], hours: int = 24) -> DeviceCountsResponse:
    """24h stacked area for the drawer — same shape as the hero chart so the
    frontend can reuse `<DeviceCountsChart />`."""
    end = datetime.now(tz=HST).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=hours - 1)
    timestamps = [(start + timedelta(hours=i)).astimezone(UTC).isoformat() for i in range(hours)]
    series: list[DeviceCountSeries] = []
    for nidx, n in enumerate(networks):
        rnd = _seeded_random(int.from_bytes(n.network_id.encode(), "big") % 9999 + nidx)
        data = []
        for i in range(hours):
            hour = i % 24
            peak = 1 if 16 <= hour <= 22 else 0.6 if 9 <= hour <= 15 else 0.25
            base = max(1, n.devices // max(1, len(networks)))
            data.append(round(base * (0.5 + peak * 0.8 + rnd() * 0.3)))
        series.append(
            DeviceCountSeries(
                network_id=n.network_id,
                network_name=n.name,
                color=n.color,
                data=data,
            )
        )
    return DeviceCountsResponse(timestamps=timestamps, series=series, ssid=None)


def build_property_detail(property_id: str) -> PropertyDetailResponse | None:
    raw = next((p for p in _PROPERTIES_RAW if p["id"] == property_id), None)
    if not raw:
        return None

    names = _NETWORK_NAMES.get(property_id, [f"Network {i + 1}" for i in range(raw["networks"])])
    # Synthesize a stable per-network ID from property + index so the color
    # rule and the dashboard pin stay consistent.
    networks: list[NetworkRow] = []
    offline_left = raw["offline"]
    for i, name in enumerate(names[: raw["networks"]]):
        nid = f"{raw['id'].upper()}-{i + 1:03d}"
        n_status: str
        if offline_left > 0:
            n_status = "offline"
            offline_left -= 1
        else:
            n_status = raw["status"] if i == 0 else "online"
        # Distribute the property's total devices roughly across networks
        share = max(0, raw["devices"] // max(1, raw["networks"]))
        networks.append(
            NetworkRow(
                network_id=nid,
                name=name,
                status=n_status,  # type: ignore[arg-type]
                devices=share if n_status == "online" else 0,
                color=color_for_network(nid),
            )
        )

    devices = _gen_devices(seed=hash(property_id) & 0xFFFF, count=min(8, max(2, raw["networks"] * 2)))

    # Roll up models / firmware for the detail-page side panels
    models: dict[str, int] = {}
    firmwares: dict[str, int] = {}
    for d in devices:
        models[d.model] = models.get(d.model, 0) + 1
        if d.firmware_version:
            firmwares[d.firmware_version] = firmwares.get(d.firmware_version, 0) + 1

    chart = _mini_chart(networks)

    return PropertyDetailResponse(
        id=raw["id"],
        name=raw["name"],
        island=raw["island"],  # type: ignore[arg-type]
        central_office=raw["co"],
        status=raw["status"],  # type: ignore[arg-type]
        address=f"Hawaii, {raw['island'].title()}",  # mock address
        networks_count=raw["networks"],
        devices_count=raw["devices"],
        uptime_pct=99.9 if raw["status"] == "online" else 96.4 if raw["status"] == "degraded" else 87.2,
        eero_models=models,
        firmware_versions=firmwares,
        chart=chart,
        networks=networks,
        devices=devices,
    )
