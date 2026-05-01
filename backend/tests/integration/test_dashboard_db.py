"""Integration smoke test for the DB-backed dashboard repo."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.common_area import CommonArea, Island, LocationType
from app.models.connected_device_count import ConnectedDeviceCount
from app.models.network_status import NetworkStatus
from app.models.property import Property
from app.services.dashboard_db import build_dashboard_db
from app.services.device_counts_db import (
    device_counts_for_property,
    ssids_for_property,
)
from app.services.property_detail_db import build_property_detail_db
from app.services.search import search_db

pytestmark = pytest.mark.integration


async def _seed(session, *, online: bool = True) -> tuple[Property, CommonArea]:
    p = Property(name="Atlas Tower", address="100 Lobby Ln")
    session.add(p)
    await session.flush()

    ca = CommonArea(
        property_id=p.id,
        location_name="Lobby",
        network_id="ATLAS-001",
        network_name="Atlas Lobby",
        island=Island.OAHU,
        location_type=LocationType.INDOOR,
        is_online=online,
    )
    session.add(ca)
    await session.flush()

    # A network_status row so /health reads a non-null last_poll
    session.add(NetworkStatus(
        common_area_id=ca.id, is_online=online, response_time_ms=12,
    ))

    # Some device-count history: total + per-SSID for the last hour
    now = datetime.now(tz=UTC)
    for offset_min in (0, 30, 60):
        ts = now - timedelta(minutes=offset_min)
        session.add(ConnectedDeviceCount(common_area_id=ca.id, count=10, ssid="", timestamp=ts))
        session.add(ConnectedDeviceCount(common_area_id=ca.id, count=6, ssid="Guest", timestamp=ts))
        session.add(ConnectedDeviceCount(common_area_id=ca.id, count=4, ssid="Staff", timestamp=ts))

    await session.commit()
    return p, ca


class TestDashboard:
    async def test_includes_seeded_property(self, db_session):
        p, ca = await _seed(db_session)
        payload = await build_dashboard_db(db_session, days=1)

        names = [pp.name for pp in payload.properties]
        assert "Atlas Tower" in names
        # Most-recent ssid="" total → 10 devices
        atlas = next(pp for pp in payload.properties if pp.name == "Atlas Tower")
        assert atlas.devices == 10
        assert atlas.status == "online"

    async def test_island_filter(self, db_session):
        await _seed(db_session)
        payload = await build_dashboard_db(db_session, island_filter="big-island", days=1)
        # Big Island has no seeded property — filtered out
        assert payload.properties == []


class TestDeviceCounts:
    async def test_totals(self, db_session):
        p, ca = await _seed(db_session)
        out = await device_counts_for_property(db_session, p.id, days=1)
        assert out.ssid is None
        assert len(out.series) == 1
        assert out.series[0].network_id == "ATLAS-001"
        # Three sample timestamps were seeded
        assert len(out.timestamps) == 3
        assert sum(out.series[0].data) == 30

    async def test_ssid_filter(self, db_session):
        p, ca = await _seed(db_session)
        out = await device_counts_for_property(db_session, p.id, days=1, ssid="Guest")
        assert out.ssid == "Guest"
        assert sum(out.series[0].data) == 18  # 6 × 3

    async def test_ssids_list(self, db_session):
        p, _ = await _seed(db_session)
        ssids = await ssids_for_property(db_session, p.id, days=7)
        assert sorted(ssids) == ["Guest", "Staff"]


class TestPropertyDetail:
    async def test_basic_payload(self, db_session):
        p, _ = await _seed(db_session)
        detail = await build_property_detail_db(db_session, p.id)
        assert detail is not None
        assert detail.name == "Atlas Tower"
        assert detail.networks_count == 1
        # uptime computed from one online network_status row → 100%
        assert detail.uptime_pct == 100.0
        assert detail.networks[0].network_id == "ATLAS-001"


class TestSearch:
    async def test_substring_match(self, db_session):
        await _seed(db_session)
        # Superuser sees everything (None scope)
        out = await search_db(db_session, "atlas", accessible_property_ids=None)
        labels = [(r.kind, r.label) for r in out]
        assert ("property", "Atlas Tower") in labels
        # network_id substring should surface as a network_id hit
        out = await search_db(db_session, "ATLAS-001", accessible_property_ids=None)
        assert any(r.kind == "network_id" and r.network_id == "ATLAS-001" for r in out)
