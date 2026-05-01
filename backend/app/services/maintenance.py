"""Maintenance service (SPEC §4.1, §6.1).

`get_affected_properties()` (the SPEC §11 checklist item) is split in two:

  • `compute_affected_property_ids()` — pure helper, takes the maintenance's
    CLLI sets + a property→CLLI lookup. Testable without a DB.
  • `get_affected_properties()` — async wrapper that queries the DB and
    delegates to the pure helper.

`island="all"` is a wildcard — every property is potentially affected
regardless of CLLI intersection (operator-entered "everywhere is going down").
"""
from __future__ import annotations

from datetime import UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.maintenance import MaintenanceIsland, ScheduledMaintenance
from app.models.property import OltClli, Property, SevenFiftyClli
from app.schemas.maintenance import (
    ClliCreate,
    MaintenanceCreate,
    MaintenanceUpdate,
)

# ──────────────────────────────────────────────────────────────────────────────
# Pure impact resolution (the SPEC §11 testable bit)
# ──────────────────────────────────────────────────────────────────────────────


def compute_affected_property_ids(
    *,
    island: str,
    olt_codes: set[str],
    seven_fifty_codes: set[str],
    properties_olt: dict[int, set[str]],
    properties_seven_fifty: dict[int, set[str]],
) -> set[int]:
    """Pure function — no DB.

    A property is affected when EITHER:
      • the maintenance's island is `"all"` AND the property has any CLLI
        that intersects, OR
      • any of its OLT or 7x50 CLLI codes intersect with the maintenance's set.

    With the `all` wildcard, an operator can flag a fleetwide event —
    we still require *some* CLLI overlap for it to count, otherwise every
    property in the system would light up regardless of which equipment
    is actually down.
    """
    all_property_ids = set(properties_olt) | set(properties_seven_fifty)

    if not olt_codes and not seven_fifty_codes:
        # No specific CLLI hooks — only meaningful if `island="all"`, in
        # which case every known property is in scope.
        return all_property_ids if island == "all" else set()

    affected: set[int] = set()
    for pid in all_property_ids:
        po = properties_olt.get(pid, set())
        ps = properties_seven_fifty.get(pid, set())
        if po & olt_codes or ps & seven_fifty_codes:
            affected.add(pid)
    return affected


# ──────────────────────────────────────────────────────────────────────────────
# Async wrapper that pulls from the DB
# ──────────────────────────────────────────────────────────────────────────────


async def get_affected_properties(
    session: AsyncSession, m: ScheduledMaintenance
) -> list[Property]:
    """Resolve which properties this maintenance window will impact.

    Pulls the property↔CLLI mappings once and delegates to the pure helper.
    """
    olt_codes = {c.clli_code for c in m.olt_cllis}
    seven_codes = {c.clli_code for c in m.seven_fifty_cllis}

    props = (
        await session.execute(
            select(Property).options(
                selectinload(Property.olt_cllis),
                selectinload(Property.seven_fifty_cllis),
            )
        )
    ).scalars().all()

    properties_olt = {p.id: {c.clli_code for c in p.olt_cllis} for p in props}
    properties_seven = {
        p.id: {c.clli_code for c in p.seven_fifty_cllis} for p in props
    }

    affected_ids = compute_affected_property_ids(
        island=m.island.value,
        olt_codes=olt_codes,
        seven_fifty_codes=seven_codes,
        properties_olt=properties_olt,
        properties_seven_fifty=properties_seven,
    )
    return [p for p in props if p.id in affected_ids]


# ──────────────────────────────────────────────────────────────────────────────
# CLLI CRUD
# ──────────────────────────────────────────────────────────────────────────────


async def create_olt_clli(session: AsyncSession, payload: ClliCreate) -> OltClli:
    c = OltClli(clli_code=payload.clli_code, description=payload.description)
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c


async def create_seven_fifty_clli(
    session: AsyncSession, payload: ClliCreate
) -> SevenFiftyClli:
    c = SevenFiftyClli(clli_code=payload.clli_code, description=payload.description)
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c


async def list_olt_cllis(session: AsyncSession) -> list[OltClli]:
    return list(
        (await session.execute(select(OltClli).order_by(OltClli.clli_code))).scalars().all()
    )


async def list_seven_fifty_cllis(session: AsyncSession) -> list[SevenFiftyClli]:
    return list(
        (
            await session.execute(
                select(SevenFiftyClli).order_by(SevenFiftyClli.clli_code)
            )
        ).scalars().all()
    )


async def delete_olt_clli(session: AsyncSession, clli_id: int) -> bool:
    obj = (
        await session.execute(select(OltClli).where(OltClli.id == clli_id))
    ).scalar_one_or_none()
    if obj is None:
        return False
    await session.delete(obj)
    await session.commit()
    return True


async def delete_seven_fifty_clli(session: AsyncSession, clli_id: int) -> bool:
    obj = (
        await session.execute(select(SevenFiftyClli).where(SevenFiftyClli.id == clli_id))
    ).scalar_one_or_none()
    if obj is None:
        return False
    await session.delete(obj)
    await session.commit()
    return True


# ──────────────────────────────────────────────────────────────────────────────
# Maintenance CRUD
# ──────────────────────────────────────────────────────────────────────────────


def _coerce_island(s: str) -> MaintenanceIsland:
    if s == "big-island":
        return MaintenanceIsland.HAWAII
    return MaintenanceIsland(s)


async def _resolve_clli_lists(
    session: AsyncSession, olt_codes: list[str], seven_codes: list[str]
) -> tuple[list[OltClli], list[SevenFiftyClli]]:
    olts: list[OltClli] = []
    if olt_codes:
        olts = list(
            (
                await session.execute(
                    select(OltClli).where(OltClli.clli_code.in_(olt_codes))
                )
            ).scalars().all()
        )
    sevens: list[SevenFiftyClli] = []
    if seven_codes:
        sevens = list(
            (
                await session.execute(
                    select(SevenFiftyClli).where(SevenFiftyClli.clli_code.in_(seven_codes))
                )
            ).scalars().all()
        )
    return olts, sevens


async def create_maintenance(
    session: AsyncSession, payload: MaintenanceCreate
) -> ScheduledMaintenance:
    olts, sevens = await _resolve_clli_lists(
        session, payload.olt_clli_codes, payload.seven_fifty_clli_codes
    )
    m = ScheduledMaintenance(
        island=_coerce_island(payload.island),
        scheduled=payload.scheduled,
        is_active=payload.is_active,
    )
    m.olt_cllis = olts
    m.seven_fifty_cllis = sevens
    session.add(m)
    await session.commit()
    await session.refresh(m)
    return m


async def update_maintenance(
    session: AsyncSession, m: ScheduledMaintenance, payload: MaintenanceUpdate
) -> ScheduledMaintenance:
    if payload.island is not None:
        m.island = _coerce_island(payload.island)
    if payload.scheduled is not None:
        m.scheduled = payload.scheduled
    if payload.is_active is not None:
        m.is_active = payload.is_active
    if payload.olt_clli_codes is not None or payload.seven_fifty_clli_codes is not None:
        olts, sevens = await _resolve_clli_lists(
            session,
            payload.olt_clli_codes or [],
            payload.seven_fifty_clli_codes or [],
        )
        if payload.olt_clli_codes is not None:
            m.olt_cllis = olts
        if payload.seven_fifty_clli_codes is not None:
            m.seven_fifty_cllis = sevens
    await session.commit()
    await session.refresh(m)
    return m


async def delete_maintenance(session: AsyncSession, m: ScheduledMaintenance) -> None:
    await session.delete(m)
    await session.commit()


async def get_maintenance(
    session: AsyncSession, m_id: int
) -> ScheduledMaintenance | None:
    return (
        await session.execute(
            select(ScheduledMaintenance)
            .options(
                selectinload(ScheduledMaintenance.olt_cllis),
                selectinload(ScheduledMaintenance.seven_fifty_cllis),
            )
            .where(ScheduledMaintenance.id == m_id)
        )
    ).scalar_one_or_none()


async def list_active_future_maintenance(
    session: AsyncSession,
) -> list[ScheduledMaintenance]:
    """SPEC §5.4 — dashboard "Scheduled Network Maintenance" card."""
    from datetime import datetime

    q = (
        select(ScheduledMaintenance)
        .options(
            selectinload(ScheduledMaintenance.olt_cllis),
            selectinload(ScheduledMaintenance.seven_fifty_cllis),
        )
        .where(
            ScheduledMaintenance.is_active.is_(True),
            ScheduledMaintenance.scheduled >= datetime.now(tz=UTC),
        )
        .order_by(ScheduledMaintenance.scheduled)
    )
    return list((await session.execute(q)).scalars().all())
