"""Unit tests for the polling state machines (SPEC §11).

The polling jobs touch a session — but all the state-machine logic lives in
the per-record helpers (`_apply_network_check`, `_apply_device_transition`)
plus the bucket-write logic in `record_device_counts`. We exercise those
with real ORM objects + a recording session + a recording notifier so we
don't need Postgres.

What's NOT covered: the top-level orchestration in `check_all_networks` /
`check_all_devices` (which is just a loop + try/except over the helpers).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.eero.client import EeroResponse
from app.models.common_area import CommonArea, Island, LocationType
from app.models.eero_device import EeroDevice
from app.models.property import Property
from app.services.notifier import NotificationPayload, Notifier
from app.services.polling import (
    DEVICE_CHRONIC_AFTER,
    DEVICE_NOTIFICATION_THROTTLE,
    NETWORK_CHRONIC_AFTER,
    _apply_device_transition,
    _apply_network_check,
    record_device_counts,
)

# ──────────────────────────────────────────────────────────────────────────────
# Test scaffolding
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class _Recorded:
    kind: str
    title: str
    message: str


class RecordingNotifier(Notifier):
    """Captures every emit so tests can assert on them."""

    def __init__(self) -> None:
        self.events: list[_Recorded] = []

    def _record(self, kind: str, area: CommonArea) -> NotificationPayload:
        prop_name = area.property.name if area.property else "?"
        msg = f"{prop_name}/{area.location_name}"
        self.events.append(_Recorded(kind, kind.replace("_", " ").upper(), msg))
        return NotificationPayload(kind, msg, 1, "x")

    async def send_network_offline(self, area):
        return self._record("network_offline", area)

    async def send_network_recovered(self, area):
        return self._record("network_recovered", area)

    async def send_device_offline(self, device, area):
        ev = self._record("device_offline", area)
        ev.message += f"@{device.serial}"
        return ev

    async def send_device_recovered(self, device, area):
        ev = self._record("device_recovered", area)
        ev.message += f"@{device.serial}"
        return ev


class FakeSession:
    """The polling helpers only need `.add()` and (in `record_device_counts`)
    `.execute()` / `.commit()` / `.delete()`. We capture all of them."""

    def __init__(self, areas: list[CommonArea] | None = None) -> None:
        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.executed: list[Any] = []
        self.commits = 0
        self._areas = areas or []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def delete(self, obj: Any) -> None:
        self.deleted.append(obj)

    async def commit(self) -> None:
        self.commits += 1

    async def execute(self, stmt: Any) -> _Result:
        self.executed.append(stmt)
        return _Result(self._areas)


@dataclass
class _Result:
    rows: list[Any]

    def scalars(self) -> _Scalars:
        return _Scalars(self.rows)


@dataclass
class _Scalars:
    rows: list[Any]

    def all(self) -> list[Any]:
        return self.rows


def _make_area(*, is_online=True, is_chronic=False, offline_since=None) -> CommonArea:
    """A minimal CommonArea with a Property attached so notifiers can format
    messages."""
    prop = Property()
    prop.id = 1
    prop.name = "Test Property"
    prop.address = None

    ca = CommonArea()
    ca.id = 10
    ca.property_id = 1
    ca.location_name = "Lobby"
    ca.network_id = "TEST-001"
    ca.island = Island.OAHU
    ca.location_type = LocationType.INDOOR
    ca.network_name = None
    ca.ssid = None
    ca.wan_ip = None
    ca.is_online = is_online
    ca.last_checked = None
    ca.offline_since = offline_since
    ca.is_chronic = is_chronic
    ca.api_endpoint = None
    ca.eero_devices = []
    ca.property = prop
    return ca


def _make_device(*, is_online=True, is_chronic=False, offline_since=None,
                 last_notification_sent=None) -> EeroDevice:
    d = EeroDevice()
    d.id = 100
    d.common_area_id = 10
    d.serial = "AABBCC"
    d.location = "Lobby"
    d.location_type = LocationType.INDOOR
    d.model = "eero Pro 6E"
    d.firmware_version = "7.0.0"
    d.is_online = is_online
    d.offline_since = offline_since
    d.is_chronic = is_chronic
    d.last_notification_sent = last_notification_sent
    return d


def _ok_response(payload: dict) -> EeroResponse:
    return EeroResponse(payload=payload, status_code=200, response_time_ms=10)


def _bad_response(err: str = "HTTP 503") -> EeroResponse:
    return EeroResponse(payload=None, status_code=503, response_time_ms=10, error_message=err)


def _now() -> datetime:
    return datetime(2026, 5, 1, 12, 0, tzinfo=UTC)


# ──────────────────────────────────────────────────────────────────────────────
# Network state machine (SPEC §5.2 + §5.3)
# ──────────────────────────────────────────────────────────────────────────────


class TestNetworkStateMachine:
    @pytest.mark.asyncio
    async def test_was_online_now_online_no_notification(self):
        """Steady-state online — no notification, no chronic flip."""
        area = _make_area(is_online=True)
        session = FakeSession()
        notifier = RecordingNotifier()

        await _apply_network_check(
            session, area, _ok_response({"status": "green"}), notifier=notifier, now=_now()
        )

        assert area.is_online is True
        assert area.offline_since is None
        assert area.is_chronic is False
        assert notifier.events == []
        # Always writes a NetworkStatus history row
        assert len(session.added) == 1

    @pytest.mark.asyncio
    async def test_offline_to_online_emits_recovered(self):
        area = _make_area(is_online=False, offline_since=_now() - timedelta(minutes=30))
        session = FakeSession()
        notifier = RecordingNotifier()

        await _apply_network_check(
            session, area, _ok_response({"status": "green"}), notifier=notifier, now=_now()
        )

        assert area.is_online is True
        assert area.offline_since is None
        assert area.is_chronic is False
        assert [e.kind for e in notifier.events] == ["network_recovered"]

    @pytest.mark.asyncio
    async def test_online_to_offline_starts_chronic_clock_and_notifies(self):
        area = _make_area(is_online=True)
        session = FakeSession()
        notifier = RecordingNotifier()
        now = _now()

        await _apply_network_check(
            session, area, _ok_response({"status": "red"}), notifier=notifier, now=now
        )

        assert area.is_online is False
        assert area.offline_since == now
        assert area.is_chronic is False  # not chronic yet
        assert [e.kind for e in notifier.events] == ["network_offline"]

    @pytest.mark.asyncio
    async def test_offline_briefly_no_chronic_no_renotify(self):
        """Was offline for 30m — still offline, not chronic, no new notification."""
        offline_since = _now() - timedelta(minutes=30)
        area = _make_area(is_online=False, offline_since=offline_since, is_chronic=False)
        session = FakeSession()
        notifier = RecordingNotifier()

        await _apply_network_check(
            session, area, _ok_response({"status": "red"}), notifier=notifier, now=_now()
        )

        assert area.is_online is False
        assert area.offline_since == offline_since  # untouched
        assert area.is_chronic is False
        assert notifier.events == []

    @pytest.mark.asyncio
    async def test_crosses_chronic_boundary_marks_chronic(self):
        """Crossed the 1h chronic threshold — flips is_chronic but doesn't re-notify."""
        offline_since = _now() - NETWORK_CHRONIC_AFTER - timedelta(seconds=1)
        area = _make_area(is_online=False, offline_since=offline_since, is_chronic=False)
        session = FakeSession()
        notifier = RecordingNotifier()

        await _apply_network_check(
            session, area, _ok_response({"status": "red"}), notifier=notifier, now=_now()
        )

        assert area.is_chronic is True
        assert notifier.events == []  # SPEC §5.3 — suppress when chronic

    @pytest.mark.asyncio
    async def test_chronic_recovery_still_emits(self):
        """Chronic-offline networks always emit recovery (SPEC §5.3)."""
        area = _make_area(
            is_online=False,
            offline_since=_now() - timedelta(hours=5),
            is_chronic=True,
        )
        session = FakeSession()
        notifier = RecordingNotifier()

        await _apply_network_check(
            session, area, _ok_response({"status": "green"}), notifier=notifier, now=_now()
        )

        assert area.is_online is True
        assert area.is_chronic is False
        assert [e.kind for e in notifier.events] == ["network_recovered"]

    @pytest.mark.asyncio
    async def test_metadata_refreshed_on_good_response(self):
        area = _make_area(is_online=True)
        session = FakeSession()
        notifier = RecordingNotifier()

        await _apply_network_check(
            session,
            area,
            _ok_response({
                "status": "green",
                "name": "Lobby/Front",
                "ssid": "Guest",
                "wan_ip": "1.2.3.4",
            }),
            notifier=notifier,
            now=_now(),
        )

        assert area.network_name == "Lobby/Front"
        assert area.ssid == "Guest"
        assert area.wan_ip == "1.2.3.4"

    @pytest.mark.asyncio
    async def test_bad_response_treats_as_offline(self):
        area = _make_area(is_online=True)
        session = FakeSession()
        notifier = RecordingNotifier()

        await _apply_network_check(
            session, area, _bad_response("HTTP 500"), notifier=notifier, now=_now()
        )

        assert area.is_online is False
        assert [e.kind for e in notifier.events] == ["network_offline"]
        # History row written with the error
        assert session.added[0].error_message == "HTTP 500"

    @pytest.mark.asyncio
    async def test_last_checked_always_updated(self):
        area = _make_area(is_online=True)
        session = FakeSession()
        now = _now()

        await _apply_network_check(
            session, area, _ok_response({"status": "green"}), notifier=RecordingNotifier(), now=now
        )

        assert area.last_checked == now


# ──────────────────────────────────────────────────────────────────────────────
# Device state machine (SPEC §5.3)
# ──────────────────────────────────────────────────────────────────────────────


class TestDeviceStateMachine:
    @pytest.mark.asyncio
    async def test_online_to_offline_starts_clock_and_notifies(self):
        device = _make_device(is_online=True)
        area = _make_area()
        notifier = RecordingNotifier()
        now = _now()

        await _apply_device_transition(device, False, area=area, notifier=notifier, now=now)

        assert device.is_online is False
        assert device.offline_since == now
        assert device.last_notification_sent == now
        assert device.is_chronic is False
        assert [e.kind for e in notifier.events] == ["device_offline"]

    @pytest.mark.asyncio
    async def test_offline_to_online_emits_recovered(self):
        device = _make_device(is_online=False, offline_since=_now() - timedelta(hours=2))
        area = _make_area()
        notifier = RecordingNotifier()

        await _apply_device_transition(device, True, area=area, notifier=notifier, now=_now())

        assert device.is_online is True
        assert device.offline_since is None
        assert device.is_chronic is False
        assert [e.kind for e in notifier.events] == ["device_recovered"]

    @pytest.mark.asyncio
    async def test_recurring_offline_throttled_to_one_per_day(self):
        """Within 24h of last_notification_sent — no re-emit (SPEC §5.3)."""
        recent = _now() - timedelta(hours=1)
        device = _make_device(
            is_online=False,
            offline_since=_now() - timedelta(hours=2),
            last_notification_sent=recent,
        )
        notifier = RecordingNotifier()

        await _apply_device_transition(device, False, area=_make_area(), notifier=notifier, now=_now())

        assert notifier.events == []
        assert device.last_notification_sent == recent  # untouched

    @pytest.mark.asyncio
    async def test_throttle_threshold_equals_chronic_threshold(self):
        """SPEC §5.3 sets device chronic = 24h and the device-offline
        throttle = 1/day. They coincide: the moment a device qualifies for
        re-notification (`last_notification_sent` ≥ 24h ago) it ALSO
        qualifies as chronic, and chronic suppression wins. So the
        re-notify branch is effectively unreachable through normal polling
        — the operator sees one alert at t=0 and then silence until either
        recovery or a manual force-check after recovery. Documenting that
        intended behaviour here so a future change doesn't accidentally
        reintroduce the spam.
        """
        old = _now() - DEVICE_NOTIFICATION_THROTTLE - timedelta(minutes=5)
        device = _make_device(
            is_online=False,
            offline_since=old,
            last_notification_sent=old,
        )
        notifier = RecordingNotifier()

        await _apply_device_transition(device, False, area=_make_area(), notifier=notifier, now=_now())

        # Marked chronic; no re-notification.
        assert device.is_chronic is True
        assert notifier.events == []

    @pytest.mark.asyncio
    async def test_crosses_chronic_boundary_marks_chronic_no_emit(self):
        """24h chronic threshold — flips is_chronic, no notification."""
        offline_since = _now() - DEVICE_CHRONIC_AFTER - timedelta(seconds=1)
        device = _make_device(
            is_online=False,
            offline_since=offline_since,
            last_notification_sent=offline_since,
        )
        notifier = RecordingNotifier()

        await _apply_device_transition(device, False, area=_make_area(), notifier=notifier, now=_now())

        assert device.is_chronic is True
        assert notifier.events == []

    @pytest.mark.asyncio
    async def test_chronic_offline_no_further_notifications(self):
        device = _make_device(
            is_online=False,
            offline_since=_now() - timedelta(days=3),
            is_chronic=True,
            last_notification_sent=_now() - timedelta(days=2),
        )
        notifier = RecordingNotifier()

        await _apply_device_transition(device, False, area=_make_area(), notifier=notifier, now=_now())

        assert notifier.events == []  # chronic suppression sticks

    @pytest.mark.asyncio
    async def test_chronic_recovery_still_emits(self):
        device = _make_device(
            is_online=False,
            offline_since=_now() - timedelta(days=3),
            is_chronic=True,
        )
        notifier = RecordingNotifier()

        await _apply_device_transition(device, True, area=_make_area(), notifier=notifier, now=_now())

        assert [e.kind for e in notifier.events] == ["device_recovered"]
        assert device.is_chronic is False


# ──────────────────────────────────────────────────────────────────────────────
# record_device_counts ⭐ (SPEC §3.4)
# ──────────────────────────────────────────────────────────────────────────────


class FakeEeroClient:
    def __init__(self, devices_response: dict | list | None, ok: bool = True) -> None:
        self._devices = devices_response
        self._ok = ok

    async def get_network(self, target):  # not exercised here
        raise NotImplementedError

    async def get_eeros(self, target):  # not exercised here
        raise NotImplementedError

    async def get_devices(self, target):
        return EeroResponse(
            payload=self._devices,
            status_code=200 if self._ok else 503,
            response_time_ms=10,
            error_message="" if self._ok else "HTTP 503",
        )


class TestRecordDeviceCounts:
    @pytest.mark.asyncio
    async def test_writes_one_total_plus_n_per_ssid(self):
        """SPEC §3.4 invariant — one ssid="" total + N per-SSID rows."""
        area = _make_area()
        session = FakeSession(areas=[area])
        client = FakeEeroClient([
            {"connected": True, "ssid": "Guest"},
            {"connected": True, "ssid": "Guest"},
            {"connected": True, "ssid": "Staff"},
            {"connected": False, "ssid": "Guest"},  # filtered out
            {"connected": True, "ssid": ""},        # bucketed as Unknown SSID
        ])

        n_written = await record_device_counts(session, client=client)

        # 1 total + 2 per-SSID (Guest, Staff) + 1 Unknown SSID = 4 rows
        assert n_written == 4
        added_counts = [r for r in session.added if r.__class__.__name__ == "ConnectedDeviceCount"]
        ssids = sorted(r.ssid for r in added_counts)
        assert ssids == ["", "Guest", "Staff", "Unknown SSID"]

        # Total row = sum of connected devices
        total_row = next(r for r in added_counts if r.ssid == "")
        assert total_row.count == 4

        # Per-SSID counts
        per = {r.ssid: r.count for r in added_counts if r.ssid != ""}
        assert per == {"Guest": 2, "Staff": 1, "Unknown SSID": 1}

        # GC always runs after the writes
        assert any("delete" in str(stmt).lower() for stmt in session.executed)
        assert session.commits == 1

    @pytest.mark.asyncio
    async def test_data_envelope_unwrap(self):
        area = _make_area()
        session = FakeSession(areas=[area])
        client = FakeEeroClient({
            "data": [{"connected": True, "ssid": "Guest"}, {"connected": True, "ssid": "Guest"}],
        })

        n = await record_device_counts(session, client=client)

        assert n == 2  # 1 total + 1 Guest
        added = [r for r in session.added if r.__class__.__name__ == "ConnectedDeviceCount"]
        assert sorted(r.ssid for r in added) == ["", "Guest"]
        assert next(r for r in added if r.ssid == "").count == 2

    @pytest.mark.asyncio
    async def test_bad_response_writes_nothing_for_that_area(self):
        area = _make_area()
        session = FakeSession(areas=[area])
        client = FakeEeroClient(None, ok=False)

        n = await record_device_counts(session, client=client)

        assert n == 0
        assert not [r for r in session.added if r.__class__.__name__ == "ConnectedDeviceCount"]
        # GC still runs
        assert session.executed
        assert session.commits == 1

    @pytest.mark.asyncio
    async def test_no_connected_devices_still_writes_zero_total(self):
        area = _make_area()
        session = FakeSession(areas=[area])
        client = FakeEeroClient([{"connected": False, "ssid": "X"}])

        n = await record_device_counts(session, client=client)

        # Just the "total" row with count=0 — per-SSID dict is empty.
        assert n == 1
        added = [r for r in session.added if r.__class__.__name__ == "ConnectedDeviceCount"]
        assert len(added) == 1
        assert added[0].ssid == "" and added[0].count == 0
