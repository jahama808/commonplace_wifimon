"""Pure functions for parsing eero API responses.

SPEC §5.2 — must be preserved verbatim:
  • online/offline determination is layered (see `determine_online`)
  • responses are sometimes nested under `data` — every reader tries both shapes
  • metadata pulled from various locations (raw, data.*, ip_settings.wan_ip, dns.wan_ip)
  • device-list response is sometimes `{data: [...]}` and sometimes `[...]`
"""
from __future__ import annotations

from typing import Any, TypedDict

# SPEC §5.2 ladder, step 1 — `health.internet.status` strings counted as online
INTERNET_STATUS_ONLINE = frozenset({"connected", "online", "up", "ok", "green"})
# Step 3 — `health.status` strings counted as online
HEALTH_STATUS_ONLINE = frozenset({"green", "yellow", "healthy", "ok"})


def unwrap(payload: Any) -> dict[str, Any]:
    """Return the inner record for envelopes that look like `{data: {...}}`.

    Eero sometimes nests, sometimes doesn't. Always pass payloads through
    this before reading fields. Returns `{}` for non-dict input so callers
    can safely use `.get(...)` without `None` checks.
    """
    if not isinstance(payload, dict):
        return {}
    inner = payload.get("data")
    if isinstance(inner, dict):
        return inner
    return payload


def determine_online(payload: Any) -> bool:
    """Layered online/offline determination (SPEC §5.2, fall through in order).

    1. health.internet.status in {connected, online, up, ok, green}
    2. health.internet.isp_up boolean
    3. health.status in {green, yellow, healthy, ok}
    4. top-level status: green/yellow online, red offline
    5. boolean fields: online, is_online, connected
    6. presence of `url` → assume online (defensive)
    7. else offline
    """
    d = unwrap(payload)
    if not d:
        return False

    health = d.get("health")
    if isinstance(health, dict):
        internet = health.get("internet")
        if isinstance(internet, dict):
            # 1
            s = internet.get("status")
            if isinstance(s, str) and s.lower() in INTERNET_STATUS_ONLINE:
                return True
            # 2
            isp_up = internet.get("isp_up")
            if isinstance(isp_up, bool):
                return isp_up
        # 3
        hs = health.get("status")
        if isinstance(hs, str) and hs.lower() in HEALTH_STATUS_ONLINE:
            return True

    # 4
    top = d.get("status")
    if isinstance(top, str):
        t = top.lower()
        if t in {"green", "yellow"}:
            return True
        if t == "red":
            return False

    # 5
    for k in ("online", "is_online", "connected"):
        v = d.get(k)
        if isinstance(v, bool):
            return v

    # 6 — defensive: presence of `url` implies online.
    # 7 — else offline.
    return bool(d.get("url"))


class NetworkMeta(TypedDict, total=False):
    network_name: str
    ssid: str
    wan_ip: str


def extract_network_metadata(payload: Any) -> NetworkMeta:
    """Pull `name`, `ssid`, `wan_ip` from the various places eero hides them."""
    d = unwrap(payload)
    out: NetworkMeta = {}

    name = d.get("name")
    if isinstance(name, str) and name:
        out["network_name"] = name

    ssid = d.get("ssid")
    if isinstance(ssid, str) and ssid:
        out["ssid"] = ssid

    wan_ip = d.get("wan_ip")
    if not wan_ip:
        ip_settings = d.get("ip_settings")
        if isinstance(ip_settings, dict):
            wan_ip = ip_settings.get("wan_ip")
    if not wan_ip:
        dns = d.get("dns")
        if isinstance(dns, dict):
            wan_ip = dns.get("wan_ip")
    if isinstance(wan_ip, str) and wan_ip:
        out["wan_ip"] = wan_ip

    return out


def extract_device_list(payload: Any) -> list[dict[str, Any]]:
    """Device-list response is sometimes `{data: [...]}` and sometimes `[...]`.

    Used by `check_all_devices` and `record_device_counts`.
    """
    if isinstance(payload, list):
        return [d for d in payload if isinstance(d, dict)]
    if isinstance(payload, dict):
        inner = payload.get("data")
        if isinstance(inner, list):
            return [d for d in inner if isinstance(d, dict)]
    return []


def bucket_connected_by_ssid(devices: list[dict[str, Any]]) -> tuple[int, dict[str, int]]:
    """SPEC §3.1 — filter to `connected: true`, bucket by `ssid`.

    Returns `(total, {ssid: count})`. Devices without an SSID are bucketed
    under `"Unknown SSID"`.
    """
    connected = [d for d in devices if d.get("connected") is True]
    counts: dict[str, int] = {}
    for d in connected:
        ssid = d.get("ssid")
        key = ssid if isinstance(ssid, str) and ssid else "Unknown SSID"
        counts[key] = counts.get(key, 0) + 1
    return len(connected), counts


def device_eero_serial(device: dict[str, Any]) -> str | None:
    """Per-eero-unit drilldown (SPEC §5.6) — count devices by `device.source.serial_number`."""
    src = device.get("source")
    if isinstance(src, dict):
        sn = src.get("serial_number")
        if isinstance(sn, str) and sn:
            return sn
    return None
