"""Deterministic mock dashboard payload.

Mirrors the design prototype's `data.jsx` so the new frontend can develop
against a stable contract before the polling pipeline is wired up. Replace
this module with real DB queries once §5.2 lands.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

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

HST = ZoneInfo("Pacific/Honolulu")

ISLANDS: list[tuple[str, str]] = [
    ("oahu", "Oahu"),
    ("maui", "Maui"),
    ("big-island", "Big Island"),
    ("kauai", "Kauai"),
]

# Color-blind-safe palette (Okabe-Ito-derived) — same list lives in the FE in
# `frontend/src/lib/series-palette.ts`. Both sides MUST stay in sync.
SERIES_PALETTE: list[str] = [
    "oklch(0.78 0.13 195)",
    "oklch(0.80 0.12 85)",
    "oklch(0.72 0.18 285)",
    "oklch(0.70 0.15 35)",
    "oklch(0.78 0.16 152)",
    "oklch(0.74 0.14 245)",
    "oklch(0.66 0.20 0)",
    "oklch(0.78 0.10 110)",
]


def color_for_network(network_id: str) -> str:
    h = 0
    for ch in network_id:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return SERIES_PALETTE[h % len(SERIES_PALETTE)]


# Lifted from design/data.jsx — the same fixtures the prototype renders.
_PROPERTIES_RAW: list[dict] = [
    {"id": "aks", "name": "Aston Kaanapali Shores", "co": "LHNAHICO", "island": "maui", "networks": 2, "status": "online",   "devices": 47,  "lat": 0.62, "lng": 0.18, "offline": 0},
    {"id": "bvk", "name": "Beach Villas at Koolina", "co": "PKAPHIXA", "island": "oahu", "networks": 4, "status": "online",   "devices": 89,  "lat": 0.45, "lng": 0.32, "offline": 0},
    {"id": "cap", "name": "Capitol Place",           "co": "HNLLHIMN", "island": "oahu", "networks": 3, "status": "online",   "devices": 64,  "lat": 0.51, "lng": 0.42, "offline": 0},
    {"id": "hbr", "name": "Hanalei Bay Resort",      "co": "KLOAHICO", "island": "kauai","networks": 1, "status": "online",   "devices": 23,  "lat": 0.22, "lng": 0.12, "offline": 0},
    {"id": "imp", "name": "Imperial Plaza",          "co": "HNLLHIXA", "island": "oahu", "networks": 1, "status": "online",   "devices": 31,  "lat": 0.55, "lng": 0.45, "offline": 0},
    {"id": "kol", "name": "Koola Lai",               "co": "—",        "island": "oahu", "networks": 2, "status": "online",   "devices": 38,  "lat": 0.48, "lng": 0.39, "offline": 0},
    {"id": "khl", "name": "Koko Head Labs",          "co": "KOKOHICO", "island": "oahu", "networks": 1, "status": "online",   "devices": 19,  "lat": 0.58, "lng": 0.50, "offline": 0},
    {"id": "owk", "name": "Owaka Street",            "co": "WLKUHIMN", "island": "maui", "networks": 1, "status": "online",   "devices": 12,  "lat": 0.65, "lng": 0.21, "offline": 0},
    {"id": "prk", "name": "Park Lane",               "co": "HNLLHIXA", "island": "oahu", "networks": 13,"status": "offline",  "devices": 218, "lat": 0.50, "lng": 0.41, "offline": 13},
    {"id": "pak", "name": "The Pakalana",            "co": "HNLLHIMN", "island": "oahu", "networks": 1, "status": "degraded", "devices": 8,   "lat": 0.53, "lng": 0.44, "offline": 1},
    {"id": "mok", "name": "Mokulele Heights",        "co": "KAHUHIMN", "island": "maui", "networks": 2, "status": "online",   "devices": 41,  "lat": 0.68, "lng": 0.25, "offline": 0},
    {"id": "kon", "name": "Kona Sands",              "co": "KAILHICO", "island": "big-island","networks": 3, "status": "online", "devices": 56, "lat": 0.82, "lng": 0.55, "offline": 0},
    {"id": "wai", "name": "Waikoloa Vista",          "co": "WIKLHICO", "island": "big-island","networks": 2, "status": "online", "devices": 33, "lat": 0.85, "lng": 0.50, "offline": 0},
    {"id": "lhi", "name": "Lahaina Pointe",          "co": "LHNAHIMN", "island": "maui", "networks": 1, "status": "online",   "devices": 18,  "lat": 0.61, "lng": 0.16, "offline": 0},
    {"id": "pri", "name": "Princeville Cliffs",      "co": "PRVLHICO", "island": "kauai","networks": 2, "status": "online",   "devices": 27,  "lat": 0.20, "lng": 0.10, "offline": 0},
]


def _seeded_random(seed: int):
    """Same LCG the prototype uses (genTimeSeries / genHeatmap) so values
    match the design pixel-for-pixel."""
    state = [seed]

    def rnd() -> float:
        state[0] = (state[0] * 9301 + 49297) % 233280
        return state[0] / 233280

    return rnd


def _gen_spark(seed: int) -> list[int]:
    rnd = _seeded_random(seed)
    out: list[int] = []
    for i in range(24):
        peak = 1 if 16 <= i <= 22 else 0.6 if 9 <= i <= 15 else 0.25
        out.append(round(8 + rnd() * 6 + peak * 18))
    return out


def _gen_heatmap(seed: int = 7) -> tuple[list[list[float]], HeatCallout, HeatCallout]:
    rnd = _seeded_random(seed)
    days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    grid: list[list[float]] = []
    peak_count = -1.0
    peak_pos = ("MON", 0)
    quiet_count = 1e9
    quiet_pos = ("MON", 0)
    for d in range(7):
        row: list[float] = []
        for h in range(24):
            base = 1 if 16 <= h <= 22 else 0.55 if 9 <= h <= 15 else 0.4 if 6 <= h <= 8 else 0.15
            noise = 0.6 + rnd() * 0.4
            count = round(min(1.0, base * noise) * 500)  # devices
            row.append(count)
            if count > peak_count:
                peak_count = count
                peak_pos = (days[d], h)
            if count < quiet_count:
                quiet_count = count
                quiet_pos = (days[d], h)
        grid.append(row)
    peak = HeatCallout(day=peak_pos[0], hour=peak_pos[1], count=int(peak_count))
    quiet = HeatCallout(day=quiet_pos[0], hour=quiet_pos[1], count=int(quiet_count))
    return grid, peak, quiet


AVAILABLE_SSIDS: list[str] = [
    "Guest",
    "Staff",
    "PoolGuest",
    "BBQ-Patio",
    "Conference",
    "Spa-Wellness",
]


def _hero_chart(days: int, ssid: str | None = None, network_seed: int = 1) -> DeviceCountsResponse:
    """Two-network stacked area sample identical in shape to genTimeSeries.

    `ssid` filters the per-network counts down to that SSID's share. The
    same timestamps drive both views (SPEC §3.4).
    """
    points = days * 24
    rnd = _seeded_random(network_seed + (sum(ord(c) for c in ssid) if ssid else 0))
    lobby: list[int] = []
    pool: list[int] = []
    timestamps: list[str] = []
    end = datetime.now(tz=HST).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=points - 1)

    # Per-SSID share factor — deterministic-ish based on the ssid string so
    # different SSIDs produce visibly different totals while keeping shape.
    share = 0.15 + (hash(ssid) & 0xFF) / 255 * 0.55 if ssid else 1.0  # 0.15..0.70 when filtered

    for i in range(points):
        hour = i % 24
        peak = 1 if 16 <= hour <= 22 else 0.6 if 9 <= hour <= 15 else 0.25
        day_boost = 1.4 if i // 24 == 1 else 1.0
        lobby.append(round((6 + rnd() * 8) * (1 + peak * 0.6) * day_boost * share))
        pool.append(round((14 + rnd() * 14) * peak * day_boost * 0.45 * share))
        timestamps.append((start + timedelta(hours=i)).astimezone(UTC).isoformat())
    series = [
        DeviceCountSeries(
            network_id="6422927",
            network_name="Lobby / Front Desk",
            color=color_for_network("6422927"),
            data=lobby,
        ),
        DeviceCountSeries(
            network_id="6422928",
            network_name="Pool / Bar",
            color=color_for_network("6422928"),
            data=pool,
        ),
    ]
    return DeviceCountsResponse(timestamps=timestamps, series=series, ssid=ssid)


def build_dashboard(
    island_filter: str | None = None,
    days: int = 7,
    ssid: str | None = None,
) -> DashboardResponse:
    raw = _PROPERTIES_RAW
    if island_filter and island_filter != "all":
        raw = [p for p in raw if p["island"] == island_filter]

    properties = [
        PropertyPin(
            id=p["id"],
            name=p["name"],
            island=p["island"],
            central_office=p["co"],
            networks=p["networks"],
            devices=p["devices"],
            status=p["status"],
            offline_count=p["offline"],
            lat=p["lat"],
            lng=p["lng"],
            spark=_gen_spark(i + 3),
        )
        for i, p in enumerate(raw)
    ]

    # Per-island summary across the unfiltered set so the tiles are stable.
    islands: list[IslandSummary] = []
    for value, label in ISLANDS:
        rows = [p for p in _PROPERTIES_RAW if p["island"] == value]
        offline = sum(p["offline"] for p in rows)
        islands.append(
            IslandSummary(
                island=value,
                label=label,
                properties=len(rows),
                networks=sum(p["networks"] for p in rows),
                devices=sum(p["devices"] for p in rows),
                offline=offline,
                status="offline" if offline > 0 else "online",
            )
        )

    alerts = [
        AlertItem(id="a1", severity="critical", time="8:42 AM", property="Park Lane",
                  network="Parking Garage / BBQ Area", device="eero Outdoor 7 — LWR STORE RM",
                  message="Device offline for 14 minutes"),
        AlertItem(id="a2", severity="warning",  time="8:31 AM", property="The Pakalana",
                  network="Pool Deck", device="eero Pro 6E — Cabana 3",
                  message="Intermittent signal, 4 disconnects in 1h"),
        AlertItem(id="a3", severity="info",     time="8:12 AM", property="Hanalei Bay Resort",
                  network="Guest WiFi", device="AP-NORTH-04",
                  message="Auto-recovered after firmware push"),
        AlertItem(id="a4", severity="critical", time="7:58 AM", property="Park Lane",
                  network="Lobby/Front Desk", device="switch-core-01",
                  message="Uplink degraded — investigating"),
        AlertItem(id="a5", severity="warning",  time="7:14 AM", property="Capitol Place",
                  network="Conference Rm 2", device="eero Pro 6E — CONF2",
                  message="High channel utilization (94%)"),
        AlertItem(id="a6", severity="info",     time="6:40 AM", property="Beach Villas at Koolina",
                  network="Maintenance LAN", device="switch-mtn-02",
                  message="Firmware update completed", acknowledged=True),
    ]

    heatmap, peak, quiet = _gen_heatmap()
    hero = _hero_chart(days=days, ssid=ssid)

    now_utc = datetime.now(tz=UTC)
    now_hst = now_utc.astimezone(HST)

    return DashboardResponse(
        generated_at=now_utc.isoformat(),
        hst_now=now_hst.strftime("%H:%M:%S"),
        total_properties=sum(i.properties for i in islands),
        total_networks=sum(i.networks for i in islands),
        total_devices=sum(i.devices for i in islands),
        avg_latency_ms=14,
        outage_count=sum(1 for p in _PROPERTIES_RAW if p["status"] == "offline"),
        degraded_count=sum(1 for p in _PROPERTIES_RAW if p["status"] == "degraded"),
        online_count=sum(1 for p in _PROPERTIES_RAW if p["status"] == "online"),
        islands=islands,
        properties=properties,
        alerts=alerts,
        hero_chart=hero,
        heatmap=heatmap,
        heatmap_peak=peak,
        heatmap_quiet=quiet,
        available_ssids=AVAILABLE_SSIDS,
        maintenance=_mock_maintenance(),
    )


def _mock_maintenance() -> list[MaintenanceWindow]:
    """Two synthetic upcoming windows so the dashboard's "Scheduled
    Maintenance" card renders something in dev mode."""
    base = datetime.now(tz=HST).replace(minute=0, second=0, microsecond=0)
    return [
        MaintenanceWindow(
            id=1,
            island="oahu",
            scheduled=(base + timedelta(days=3, hours=2)).astimezone(UTC).isoformat(),
            olt_clli_codes=["HNLLHIXAOLT01"],
            seven_fifty_clli_codes=[],
            affected_property_names=["Park Lane", "Imperial Plaza", "The Pakalana"],
        ),
        MaintenanceWindow(
            id=2,
            island="all",
            scheduled=(base + timedelta(days=14)).astimezone(UTC).isoformat(),
            olt_clli_codes=[],
            seven_fifty_clli_codes=[],
            affected_property_names=[],  # fleetwide notice, no equipment hooks
        ),
    ]
