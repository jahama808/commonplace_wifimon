"""Integration tests for `yaml_importer.apply` against a real DB."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.common_area import CommonArea
from app.models.property import OltClli, Property
from app.services.yaml_importer import apply, load_yaml_str, plan

pytestmark = pytest.mark.integration


SEED = """
properties:
  - name: Aston Kaanapali Shores
    address: 45 Kai Ala Dr, Lahaina, HI 96761
    island: maui
    olt_cllis: [LHNAHIXAOLT01]
    common_areas:
      - location_name: Lobby / Front Desk
        location_type: indoor
        network_id: "AKS-001"
      - location_name: Pool / Bar
        location_type: outdoor
        network_id: "AKS-002"
"""


class TestApply:
    async def test_apply_creates_everything_then_idempotent(self, db_session, db_engine):
        from sqlalchemy.ext.asyncio import async_sessionmaker

        sm = async_sessionmaker(db_engine, expire_on_commit=False)
        doc = load_yaml_str(SEED)

        # First pass: empty DB → all creates
        async with sm() as s:
            p = await plan(s, doc)
            assert {op.op for op in p.properties} == {"create"}
            assert {op.op for op in p.areas} == {"create"}
        async with sm() as s:
            p = await plan(s, doc)
            counts = await apply(s, p)
            assert counts["properties_changed"] == 1
            assert counts["areas_changed"] == 2

        # Verify
        async with sm() as s:
            props = (await s.execute(select(Property))).scalars().all()
            areas = (await s.execute(select(CommonArea))).scalars().all()
            assert len(props) == 1 and props[0].name == "Aston Kaanapali Shores"
            assert {a.network_id for a in areas} == {"AKS-001", "AKS-002"}

        # Second pass: same YAML → zero-op plan
        async with sm() as s:
            p = await plan(s, doc)
            assert all(op.op == "noop" for op in p.properties)
            assert all(op.op == "noop" for op in p.areas)
            assert not p.has_changes

    async def test_apply_creates_olt_clli_referenced_by_property(self, db_session, db_engine):
        from sqlalchemy.ext.asyncio import async_sessionmaker

        sm = async_sessionmaker(db_engine, expire_on_commit=False)
        doc = load_yaml_str(SEED)
        async with sm() as s:
            await apply(s, await plan(s, doc))

        # The CLLI was auto-created by apply()
        async with sm() as s:
            clli = (
                await s.execute(
                    select(OltClli).where(OltClli.clli_code == "LHNAHIXAOLT01")
                )
            ).scalar_one_or_none()
            assert clli is not None

    async def test_update_path_changes_address(self, db_session, db_engine):
        from sqlalchemy.ext.asyncio import async_sessionmaker

        sm = async_sessionmaker(db_engine, expire_on_commit=False)
        doc = load_yaml_str(SEED)
        async with sm() as s:
            await apply(s, await plan(s, doc))

        # Mutate the YAML and re-import
        doc2 = load_yaml_str(SEED.replace(
            "45 Kai Ala Dr, Lahaina, HI 96761",
            "NEW ADDR",
        ))
        async with sm() as s:
            p = await plan(s, doc2)
            assert any(op.op == "update" and "address" in op.diff for op in p.properties)
            await apply(s, p)

        async with sm() as s:
            prop = (
                await s.execute(select(Property).where(Property.name == "Aston Kaanapali Shores"))
            ).scalar_one()
            assert prop.address == "NEW ADDR"

    async def test_allow_deletes_removes_orphan(self, db_session, db_engine):
        from sqlalchemy.ext.asyncio import async_sessionmaker

        sm = async_sessionmaker(db_engine, expire_on_commit=False)

        # Seed something not in the YAML
        async with sm() as s:
            s.add(Property(name="To Be Removed"))
            await s.commit()

        # Empty YAML — without allow_deletes nothing happens
        async with sm() as s:
            p = await plan(s, load_yaml_str("properties: []"), allow_deletes=False)
            assert not p.has_changes

        # With allow_deletes → orphan is queued for delete and removed
        async with sm() as s:
            p = await plan(s, load_yaml_str("properties: []"), allow_deletes=True)
            assert any(op.op == "delete" for op in p.properties)
            await apply(s, p)

        async with sm() as s:
            assert (await s.execute(select(Property))).scalars().all() == []
