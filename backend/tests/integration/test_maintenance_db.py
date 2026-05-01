"""Integration test for `get_affected_properties` against real M:N rows."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.maintenance import MaintenanceIsland, ScheduledMaintenance
from app.models.property import OltClli, Property, SevenFiftyClli
from app.services.maintenance import (
    get_affected_properties,
    list_active_future_maintenance,
)

pytestmark = pytest.mark.integration


async def _seed(session) -> dict:
    olt_a = OltClli(clli_code="OLT-A")
    olt_b = OltClli(clli_code="OLT-B")
    seven = SevenFiftyClli(clli_code="750-X")
    session.add_all([olt_a, olt_b, seven])
    await session.flush()

    p1 = Property(name="P1")
    p2 = Property(name="P2")
    p3 = Property(name="P3")
    p1.olt_cllis = [olt_a]
    p2.olt_cllis = [olt_b]
    p3.seven_fifty_cllis = [seven]
    session.add_all([p1, p2, p3])

    m_olt_a = ScheduledMaintenance(
        island=MaintenanceIsland.OAHU,
        scheduled=datetime.now(tz=UTC) + timedelta(days=2),
        is_active=True,
    )
    m_olt_a.olt_cllis = [olt_a]
    m_seven = ScheduledMaintenance(
        island=MaintenanceIsland.MAUI,
        scheduled=datetime.now(tz=UTC) + timedelta(days=3),
        is_active=True,
    )
    m_seven.seven_fifty_cllis = [seven]
    m_inactive = ScheduledMaintenance(
        island=MaintenanceIsland.OAHU,
        scheduled=datetime.now(tz=UTC) + timedelta(days=1),
        is_active=False,
    )
    m_past = ScheduledMaintenance(
        island=MaintenanceIsland.OAHU,
        scheduled=datetime.now(tz=UTC) - timedelta(days=1),
        is_active=True,
    )
    session.add_all([m_olt_a, m_seven, m_inactive, m_past])
    await session.commit()
    return {
        "p1": p1, "p2": p2, "p3": p3,
        "m_olt_a": m_olt_a, "m_seven": m_seven,
        "m_inactive": m_inactive, "m_past": m_past,
    }


class TestGetAffectedProperties:
    async def test_olt_intersection_picks_one(self, db_session):
        s = await _seed(db_session)
        # Reload with relationships hydrated
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        m = (
            await db_session.execute(
                select(ScheduledMaintenance)
                .options(
                    selectinload(ScheduledMaintenance.olt_cllis),
                    selectinload(ScheduledMaintenance.seven_fifty_cllis),
                )
                .where(ScheduledMaintenance.id == s["m_olt_a"].id)
            )
        ).scalar_one()

        affected = await get_affected_properties(db_session, m)
        assert {p.name for p in affected} == {"P1"}

    async def test_seven_fifty_intersection_picks_one(self, db_session):
        s = await _seed(db_session)
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        m = (
            await db_session.execute(
                select(ScheduledMaintenance)
                .options(
                    selectinload(ScheduledMaintenance.olt_cllis),
                    selectinload(ScheduledMaintenance.seven_fifty_cllis),
                )
                .where(ScheduledMaintenance.id == s["m_seven"].id)
            )
        ).scalar_one()

        affected = await get_affected_properties(db_session, m)
        assert {p.name for p in affected} == {"P3"}


class TestListActiveFutureMaintenance:
    async def test_filters_inactive_and_past(self, db_session):
        await _seed(db_session)
        active = await list_active_future_maintenance(db_session)
        # Only the two active future ones
        assert len(active) == 2
        # Sorted by scheduled timestamp (asc)
        assert active[0].scheduled < active[1].scheduled
