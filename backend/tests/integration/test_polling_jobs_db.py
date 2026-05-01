"""Integration test for the polling jobs (SPEC §11).

Stands up a fake EeroClient that returns canned responses, runs one tick of
each job, and asserts the right rows landed in the DB.

Closes the SPEC §11 line item:
> Integration: a fake eero server (httpx-mock) feeding the worker;
> verify DB state after a tick.
"""
from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from app.eero.client import EeroResponse
from app.models.common_area import CommonArea, Island, LocationType
from app.models.connected_device_count import ConnectedDeviceCount
from app.models.eero_device import EeroDevice
from app.models.network_status import NetworkStatus
from app.models.property import Property
from app.services.notifier import NullNotifier
from app.services.polling import (
    check_all_devices,
    check_all_networks,
    record_device_counts,
)

pytestmark = pytest.mark.integration


# ──────────────────────────────────────────────────────────────────────────────
# Fake eero client — same shape as `_FakeEeroClient` in test_admin.py
# ──────────────────────────────────────────────────────────────────────────────


class FakeEero:
    def __init__(
        self,
        *,
        network_payload: Any = None,
        eeros_payload: Any = None,
        devices_payload: Any = None,
        ok: bool = True,
    ) -> None:
        self.network_payload = network_payload
        self.eeros_payload = eeros_payload
        self.devices_payload = devices_payload
        self.ok = ok

    def _resp(self, payload: Any) -> EeroResponse:
        return EeroResponse(
            payload=payload,
            status_code=200 if self.ok else 503,
            response_time_ms=10,
            error_message="" if self.ok else "HTTP 503",
        )

    async def get_network(self, target):
        return self._resp(self.network_payload)

    async def get_eeros(self, target):
        return self._resp(self.eeros_payload)

    async def get_devices(self, target):
        return self._resp(self.devices_payload)


async def _seed_property_with_one_area(session) -> CommonArea:
    p = Property(name="Polling Property")
    session.add(p)
    await session.flush()
    ca = CommonArea(
        property_id=p.id,
        location_name="Lobby",
        network_id="POLL-001",
        island=Island.OAHU,
        location_type=LocationType.INDOOR,
        is_online=False,  # start offline so first online tick is a transition
    )
    session.add(ca)
    await session.commit()
    await session.refresh(ca)
    return ca


# ──────────────────────────────────────────────────────────────────────────────
# check_all_networks
# ──────────────────────────────────────────────────────────────────────────────


class TestCheckAllNetworks:
    async def test_writes_history_row_and_updates_state(self, db_session):
        ca = await _seed_property_with_one_area(db_session)
        client = FakeEero(network_payload={
            "name": "Lobby Net",
            "ssid": "Guest",
            "wan_ip": "1.2.3.4",
            "status": "green",
        })

        n = await check_all_networks(
            db_session, client=client, notifier=NullNotifier(), force=True
        )
        assert n == 1

        # State was updated
        await db_session.refresh(ca)
        assert ca.is_online is True
        assert ca.network_name == "Lobby Net"
        assert ca.ssid == "Guest"
        assert ca.wan_ip == "1.2.3.4"
        assert ca.last_checked is not None

        # History row written
        rows = (
            await db_session.execute(
                select(NetworkStatus).where(NetworkStatus.common_area_id == ca.id)
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].is_online is True
        assert rows[0].response_time_ms == 10
        assert rows[0].raw_response is not None  # JSONB stored as dict

    async def test_offline_response_writes_offline_row(self, db_session):
        ca = await _seed_property_with_one_area(db_session)
        # Pre-mark online so we record a real transition
        ca.is_online = True
        await db_session.commit()

        client = FakeEero(network_payload={"status": "red"})
        await check_all_networks(
            db_session, client=client, notifier=NullNotifier(), force=True
        )

        await db_session.refresh(ca)
        assert ca.is_online is False
        assert ca.offline_since is not None


# ──────────────────────────────────────────────────────────────────────────────
# check_all_devices
# ──────────────────────────────────────────────────────────────────────────────


class TestCheckAllDevices:
    async def test_upserts_eero_units(self, db_session):
        ca = await _seed_property_with_one_area(db_session)
        client = FakeEero(eeros_payload=[
            {"serial": "AA-1", "model": "eero Pro 6E", "online": True, "location": "Lobby"},
            {"serial": "AA-2", "model": "eero Outdoor 7", "online": False, "location": "Garage"},
        ])

        n = await check_all_devices(db_session, client=client, notifier=NullNotifier())
        assert n == 1

        rows = (
            await db_session.execute(
                select(EeroDevice).where(EeroDevice.common_area_id == ca.id)
            )
        ).scalars().all()
        by_serial = {d.serial: d for d in rows}
        assert set(by_serial) == {"AA-1", "AA-2"}
        assert by_serial["AA-1"].is_online is True
        assert by_serial["AA-2"].is_online is False
        assert by_serial["AA-2"].offline_since is not None

    async def test_vanished_device_is_deleted(self, db_session):
        ca = await _seed_property_with_one_area(db_session)
        client = FakeEero(eeros_payload=[
            {"serial": "AA-1", "model": "eero Pro 6E", "online": True},
            {"serial": "AA-2", "model": "eero Pro 6E", "online": True},
        ])
        await check_all_devices(db_session, client=client, notifier=NullNotifier())

        # Remove AA-2 from the response
        client = FakeEero(eeros_payload=[
            {"serial": "AA-1", "model": "eero Pro 6E", "online": True},
        ])
        await check_all_devices(db_session, client=client, notifier=NullNotifier())

        rows = (
            await db_session.execute(
                select(EeroDevice).where(EeroDevice.common_area_id == ca.id)
            )
        ).scalars().all()
        assert {d.serial for d in rows} == {"AA-1"}


# ──────────────────────────────────────────────────────────────────────────────
# record_device_counts ⭐
# ──────────────────────────────────────────────────────────────────────────────


class TestRecordDeviceCounts:
    async def test_writes_total_plus_per_ssid(self, db_session):
        ca = await _seed_property_with_one_area(db_session)
        client = FakeEero(devices_payload=[
            {"connected": True, "ssid": "Guest"},
            {"connected": True, "ssid": "Guest"},
            {"connected": True, "ssid": "Staff"},
            {"connected": False, "ssid": "Guest"},  # skipped
        ])

        n = await record_device_counts(db_session, client=client)
        # 1 total + 2 per-SSID
        assert n == 3

        rows = (
            await db_session.execute(
                select(ConnectedDeviceCount).where(
                    ConnectedDeviceCount.common_area_id == ca.id
                )
            )
        ).scalars().all()
        by_ssid = {r.ssid: r.count for r in rows}
        assert by_ssid == {"": 3, "Guest": 2, "Staff": 1}
