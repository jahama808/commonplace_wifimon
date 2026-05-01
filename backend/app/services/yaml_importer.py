"""Idempotent YAML import (SPEC §6.1).

Three-step flow:

  1. `load_yaml(path)` parses + validates the file.
  2. `plan(session, file, allow_deletes)` diffs against the DB and returns
     a typed `ImportPlan` (creates / updates / deletes).
  3. `apply(session, plan)` executes the plan in a single transaction.

Re-running an unchanged file produces a zero-op plan.

Property identity = `name` (matches `Property.name UNIQUE` constraint).
Common-area identity = `network_id` (matches `CommonArea.network_id UNIQUE`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.common_area import CommonArea, LocationType
from app.models.common_area import Island as IslandEnum
from app.models.property import OltClli, Property, SevenFiftyClli
from app.schemas.import_yaml import (
    CommonAreaSpec,
    ImportFile,
    PropertySpec,
)

# ──────────────────────────────────────────────────────────────────────────────
# Plan shape
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class PropertyOp:
    op: str  # "create" | "update" | "delete" | "noop"
    name: str
    spec: PropertySpec | None = None  # None for delete
    db_id: int | None = None  # set for update / delete
    diff: dict[str, tuple] = field(default_factory=dict)  # field -> (old, new) for update


@dataclass
class AreaOp:
    op: str  # "create" | "update" | "delete" | "noop"
    network_id: str
    property_name: str  # for log/diff display
    spec: CommonAreaSpec | None = None
    db_id: int | None = None
    diff: dict[str, tuple] = field(default_factory=dict)


@dataclass
class ImportPlan:
    properties: list[PropertyOp] = field(default_factory=list)
    areas: list[AreaOp] = field(default_factory=list)
    allow_deletes: bool = False

    @property
    def has_changes(self) -> bool:
        return any(p.op != "noop" for p in self.properties) or any(
            a.op != "noop" for a in self.areas
        )

    def summary(self) -> dict[str, int]:
        return {
            "properties_create": sum(1 for p in self.properties if p.op == "create"),
            "properties_update": sum(1 for p in self.properties if p.op == "update"),
            "properties_delete": sum(1 for p in self.properties if p.op == "delete"),
            "properties_noop": sum(1 for p in self.properties if p.op == "noop"),
            "areas_create": sum(1 for a in self.areas if a.op == "create"),
            "areas_update": sum(1 for a in self.areas if a.op == "update"),
            "areas_delete": sum(1 for a in self.areas if a.op == "delete"),
            "areas_noop": sum(1 for a in self.areas if a.op == "noop"),
        }


# ──────────────────────────────────────────────────────────────────────────────
# Parser
# ──────────────────────────────────────────────────────────────────────────────


def load_yaml(path: str | Path) -> ImportFile:
    text = Path(path).read_text(encoding="utf-8")
    raw = yaml.safe_load(text) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"YAML root must be a mapping, got {type(raw).__name__}")
    # Pydantic validation surfaces friendly errors.
    return ImportFile.model_validate(raw)


def load_yaml_str(text: str) -> ImportFile:
    raw = yaml.safe_load(text) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"YAML root must be a mapping, got {type(raw).__name__}")
    return ImportFile.model_validate(raw)


# ──────────────────────────────────────────────────────────────────────────────
# Diff helpers
# ──────────────────────────────────────────────────────────────────────────────


def _coerce_island(s: str | None) -> IslandEnum | None:
    if s is None:
        return None
    if s == "big-island":
        return IslandEnum.HAWAII
    try:
        return IslandEnum(s)
    except ValueError:
        return None


def _diff_property(spec: PropertySpec, existing: Property) -> dict[str, tuple]:
    diff: dict[str, tuple] = {}
    if (spec.address or None) != (existing.address or None):
        diff["address"] = (existing.address, spec.address)
    return diff


def _diff_area(
    spec: CommonAreaSpec, existing: CommonArea, *, default_island: str | None
) -> dict[str, tuple]:
    diff: dict[str, tuple] = {}
    if spec.location_name != existing.location_name:
        diff["location_name"] = (existing.location_name, spec.location_name)
    desired_island = _coerce_island(spec.island or default_island)
    if desired_island != existing.island:
        diff["island"] = (
            existing.island.value if existing.island else None,
            desired_island.value if desired_island else None,
        )
    desired_lt = LocationType(spec.location_type)
    if desired_lt != existing.location_type:
        diff["location_type"] = (existing.location_type.value, desired_lt.value)
    if (spec.description or None) != (existing.description or None):
        diff["description"] = (existing.description, spec.description)
    if (spec.api_endpoint or None) != (existing.api_endpoint or None):
        diff["api_endpoint"] = (existing.api_endpoint, spec.api_endpoint)
    return diff


# ──────────────────────────────────────────────────────────────────────────────
# Planner
# ──────────────────────────────────────────────────────────────────────────────


async def plan(
    session: AsyncSession, file: ImportFile, *, allow_deletes: bool = False
) -> ImportPlan:
    out = ImportPlan(allow_deletes=allow_deletes)

    # Snapshot DB
    db_props = (
        await session.execute(
            select(Property).options(
                selectinload(Property.common_areas),
                selectinload(Property.olt_cllis),
                selectinload(Property.seven_fifty_cllis),
            )
        )
    ).scalars().all()
    db_props_by_name = {p.name: p for p in db_props}
    db_areas_by_nid: dict[str, CommonArea] = {}
    for p in db_props:
        for ca in p.common_areas:
            db_areas_by_nid[ca.network_id] = ca

    spec_prop_names: set[str] = set()
    spec_area_nids: set[str] = set()

    for prop_spec in file.properties:
        spec_prop_names.add(prop_spec.name)
        existing = db_props_by_name.get(prop_spec.name)
        if existing is None:
            out.properties.append(
                PropertyOp(op="create", name=prop_spec.name, spec=prop_spec)
            )
        else:
            d = _diff_property(prop_spec, existing)
            if d:
                out.properties.append(
                    PropertyOp(
                        op="update",
                        name=prop_spec.name,
                        spec=prop_spec,
                        db_id=existing.id,
                        diff=d,
                    )
                )
            else:
                out.properties.append(
                    PropertyOp(op="noop", name=prop_spec.name, spec=prop_spec, db_id=existing.id)
                )

        for area_spec in prop_spec.common_areas:
            spec_area_nids.add(area_spec.network_id)
            ex_area = db_areas_by_nid.get(area_spec.network_id)
            if ex_area is None:
                out.areas.append(
                    AreaOp(
                        op="create",
                        network_id=area_spec.network_id,
                        property_name=prop_spec.name,
                        spec=area_spec,
                    )
                )
            else:
                d = _diff_area(area_spec, ex_area, default_island=prop_spec.island)
                if d:
                    out.areas.append(
                        AreaOp(
                            op="update",
                            network_id=area_spec.network_id,
                            property_name=prop_spec.name,
                            spec=area_spec,
                            db_id=ex_area.id,
                            diff=d,
                        )
                    )
                else:
                    out.areas.append(
                        AreaOp(
                            op="noop",
                            network_id=area_spec.network_id,
                            property_name=prop_spec.name,
                            spec=area_spec,
                            db_id=ex_area.id,
                        )
                    )

    # Deletes — only emitted when allow_deletes=True
    if allow_deletes:
        for name, p in db_props_by_name.items():
            if name not in spec_prop_names:
                out.properties.append(PropertyOp(op="delete", name=name, db_id=p.id))
        for nid, ca in db_areas_by_nid.items():
            # Only flag an area-level delete if its owning property survives.
            # (If the property itself is being deleted, FK cascade handles areas.)
            if nid not in spec_area_nids and (
                ca.property is None
                or (ca.property is not None and ca.property.name in spec_prop_names)
            ):
                out.areas.append(
                    AreaOp(
                        op="delete",
                        network_id=nid,
                        property_name=ca.property.name if ca.property else "?",
                        db_id=ca.id,
                    )
                )

    return out


# ──────────────────────────────────────────────────────────────────────────────
# Apply
# ──────────────────────────────────────────────────────────────────────────────


async def apply(session: AsyncSession, plan_obj: ImportPlan) -> dict[str, int]:
    """Execute every non-noop op. Returns a count summary."""
    counts = {"properties_changed": 0, "areas_changed": 0, "deleted": 0}

    # Re-fetch CLLI lookups so we can attach them by code
    olt_by_code: dict[str, OltClli] = {
        c.clli_code: c
        for c in (await session.execute(select(OltClli))).scalars().all()
    }
    seven_by_code: dict[str, SevenFiftyClli] = {
        c.clli_code: c
        for c in (await session.execute(select(SevenFiftyClli))).scalars().all()
    }

    # Build a name→Property cache as we go (creates need to be visible to area ops)
    props_by_name: dict[str, Property] = {
        p.name: p
        for p in (
            await session.execute(
                select(Property).options(
                    selectinload(Property.olt_cllis),
                    selectinload(Property.seven_fifty_cllis),
                )
            )
        ).scalars().all()
    }

    for op in plan_obj.properties:
        if op.op == "create":
            assert op.spec is not None
            p = Property(name=op.spec.name, address=op.spec.address)
            for code in op.spec.olt_cllis:
                clli = olt_by_code.get(code) or _make_olt(code, olt_by_code)
                p.olt_cllis.append(clli)
            for code in op.spec.seven_fifty_cllis:
                clli = seven_by_code.get(code) or _make_seven(code, seven_by_code)
                p.seven_fifty_cllis.append(clli)
            session.add(p)
            await session.flush()  # need p.id for area ops
            props_by_name[p.name] = p
            counts["properties_changed"] += 1
        elif op.op == "update":
            assert op.spec is not None and op.db_id is not None
            p = props_by_name.get(op.name) or (
                await session.execute(select(Property).where(Property.id == op.db_id))
            ).scalar_one()
            if "address" in op.diff:
                p.address = op.spec.address
            counts["properties_changed"] += 1
        elif op.op == "delete":
            assert op.db_id is not None and plan_obj.allow_deletes
            p = (
                await session.execute(select(Property).where(Property.id == op.db_id))
            ).scalar_one_or_none()
            if p is not None:
                await session.delete(p)
                counts["deleted"] += 1

    for op in plan_obj.areas:
        if op.op == "create":
            assert op.spec is not None
            parent = props_by_name.get(op.property_name)
            if parent is None:
                # Safety: parent must exist (the YAML's property was either
                # already present or in this same plan as a `create`).
                continue
            ca = CommonArea(
                property_id=parent.id,
                location_name=op.spec.location_name,
                network_id=op.spec.network_id,
                island=_coerce_island(op.spec.island or _yaml_island_for(plan_obj, op.property_name)),
                location_type=LocationType(op.spec.location_type),
                description=op.spec.description,
                api_endpoint=op.spec.api_endpoint,
            )
            session.add(ca)
            counts["areas_changed"] += 1
        elif op.op == "update":
            assert op.spec is not None and op.db_id is not None
            ca = (
                await session.execute(select(CommonArea).where(CommonArea.id == op.db_id))
            ).scalar_one()
            if "location_name" in op.diff:
                ca.location_name = op.spec.location_name
            if "island" in op.diff:
                ca.island = _coerce_island(op.spec.island or _yaml_island_for(plan_obj, op.property_name))
            if "location_type" in op.diff:
                ca.location_type = LocationType(op.spec.location_type)
            if "description" in op.diff:
                ca.description = op.spec.description
            if "api_endpoint" in op.diff:
                ca.api_endpoint = op.spec.api_endpoint
            counts["areas_changed"] += 1
        elif op.op == "delete":
            assert op.db_id is not None and plan_obj.allow_deletes
            ca = (
                await session.execute(select(CommonArea).where(CommonArea.id == op.db_id))
            ).scalar_one_or_none()
            if ca is not None:
                await session.delete(ca)
                counts["deleted"] += 1

    await session.commit()
    return counts


def _make_olt(code: str, cache: dict[str, OltClli]) -> OltClli:
    c = OltClli(clli_code=code)
    cache[code] = c
    return c


def _make_seven(code: str, cache: dict[str, SevenFiftyClli]) -> SevenFiftyClli:
    c = SevenFiftyClli(clli_code=code)
    cache[code] = c
    return c


def _yaml_island_for(plan_obj: ImportPlan, property_name: str) -> str | None:
    """Walk the planned property ops to find the property-level island for
    fallback when an area spec doesn't specify one."""
    for op in plan_obj.properties:
        if op.name == property_name and op.spec is not None:
            return op.spec.island
    return None
