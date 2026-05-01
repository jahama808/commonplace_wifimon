"""Tests for the YAML importer (SPEC §6.1).

Parser + planner are exercised against fixture YAML and a fake session
that snapshots the ORM rows the planner queries. Apply isn't exercised
here because it touches a real DB; cover that with an integration test
once Postgres is wired up.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.models.common_area import CommonArea, Island, LocationType
from app.models.property import Property
from app.services.yaml_importer import (
    load_yaml_str,
    plan,
)

# ──────────────────────────────────────────────────────────────────────────────
# Scaffolding
# ──────────────────────────────────────────────────────────────────────────────


def _make_property(
    *, id: int, name: str, address: str | None = None, common_areas=None
) -> Property:
    p = Property()
    p.id = id
    p.name = name
    p.address = address
    p.common_areas = list(common_areas or [])
    p.olt_cllis = []
    p.seven_fifty_cllis = []
    for ca in p.common_areas:
        ca.property = p
        ca.property_id = id
    return p


def _make_area(
    *, id: int, network_id: str, location_name: str,
    island: Island | None = None,
    location_type: LocationType = LocationType.INDOOR,
    description: str | None = None,
    api_endpoint: str | None = None,
) -> CommonArea:
    ca = CommonArea()
    ca.id = id
    ca.network_id = network_id
    ca.location_name = location_name
    ca.island = island
    ca.location_type = location_type
    ca.description = description
    ca.api_endpoint = api_endpoint
    ca.network_name = None
    ca.ssid = None
    ca.wan_ip = None
    return ca


@dataclass
class _Result:
    rows: list

    def scalars(self):
        return self

    def all(self):
        return self.rows


class FakeSession:
    """Returns properties (with selectinload) to the planner; ignores other queries."""

    def __init__(self, properties: list[Property]) -> None:
        self.properties = properties

    async def execute(self, _stmt):
        return _Result(self.properties)


# ──────────────────────────────────────────────────────────────────────────────
# Parser
# ──────────────────────────────────────────────────────────────────────────────


SAMPLE_YAML = """
properties:
  - name: Kapahulu Tower
    address: 1234 Kapahulu Ave, Honolulu, HI
    island: oahu
    olt_cllis: [HNLLHIXAOLT01]
    common_areas:
      - location_name: Lobby
        location_type: indoor
        network_id: "6422927"
      - location_name: Pool Deck
        location_type: outdoor
        network_id: "6422928"
"""


class TestLoadYaml:
    def test_basic_parse(self):
        doc = load_yaml_str(SAMPLE_YAML)
        assert len(doc.properties) == 1
        p = doc.properties[0]
        assert p.name == "Kapahulu Tower"
        assert p.island == "oahu"
        assert p.olt_cllis == ["HNLLHIXAOLT01"]
        assert len(p.common_areas) == 2
        assert p.common_areas[0].location_name == "Lobby"
        assert p.common_areas[0].location_type == "indoor"
        assert p.common_areas[1].location_type == "outdoor"

    def test_empty_file_parses_to_empty_list(self):
        doc = load_yaml_str("properties: []")
        assert doc.properties == []

    def test_root_must_be_mapping(self):
        with pytest.raises(ValueError):
            load_yaml_str("- just\n- a list")

    def test_validation_error_on_missing_required_field(self):
        # `name` is required on PropertySpec
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            load_yaml_str("properties:\n  - address: foo\n")


# ──────────────────────────────────────────────────────────────────────────────
# Planner
# ──────────────────────────────────────────────────────────────────────────────


class TestPlanner:
    @pytest.mark.asyncio
    async def test_create_property_and_areas_from_empty_db(self):
        doc = load_yaml_str(SAMPLE_YAML)
        session = FakeSession(properties=[])

        result = await plan(session, doc)

        assert [p.op for p in result.properties] == ["create"]
        assert sorted(a.op for a in result.areas) == ["create", "create"]
        s = result.summary()
        assert s["properties_create"] == 1
        assert s["areas_create"] == 2

    @pytest.mark.asyncio
    async def test_idempotent_when_db_matches_yaml(self):
        doc = load_yaml_str(SAMPLE_YAML)
        existing = _make_property(
            id=1,
            name="Kapahulu Tower",
            address="1234 Kapahulu Ave, Honolulu, HI",
            common_areas=[
                _make_area(id=10, network_id="6422927", location_name="Lobby",
                           island=Island.OAHU, location_type=LocationType.INDOOR),
                _make_area(id=11, network_id="6422928", location_name="Pool Deck",
                           island=Island.OAHU, location_type=LocationType.OUTDOOR),
            ],
        )
        session = FakeSession(properties=[existing])

        result = await plan(session, doc)

        # Re-running an unchanged YAML → zero-op plan
        assert all(p.op == "noop" for p in result.properties)
        assert all(a.op == "noop" for a in result.areas)
        assert not result.has_changes

    @pytest.mark.asyncio
    async def test_property_address_change_detected(self):
        doc = load_yaml_str(SAMPLE_YAML)
        existing = _make_property(
            id=1, name="Kapahulu Tower", address="OLD ADDRESS",
            common_areas=[
                _make_area(id=10, network_id="6422927", location_name="Lobby",
                           island=Island.OAHU, location_type=LocationType.INDOOR),
                _make_area(id=11, network_id="6422928", location_name="Pool Deck",
                           island=Island.OAHU, location_type=LocationType.OUTDOOR),
            ],
        )
        session = FakeSession(properties=[existing])

        result = await plan(session, doc)
        prop = result.properties[0]
        assert prop.op == "update"
        assert "address" in prop.diff
        assert prop.diff["address"][1] == "1234 Kapahulu Ave, Honolulu, HI"
        assert all(a.op == "noop" for a in result.areas)

    @pytest.mark.asyncio
    async def test_area_location_name_change_detected(self):
        doc = load_yaml_str(SAMPLE_YAML)
        existing = _make_property(
            id=1, name="Kapahulu Tower", address="1234 Kapahulu Ave, Honolulu, HI",
            common_areas=[
                _make_area(id=10, network_id="6422927", location_name="OLD LOBBY",
                           island=Island.OAHU, location_type=LocationType.INDOOR),
                _make_area(id=11, network_id="6422928", location_name="Pool Deck",
                           island=Island.OAHU, location_type=LocationType.OUTDOOR),
            ],
        )
        session = FakeSession(properties=[existing])

        result = await plan(session, doc)
        ops = {a.network_id: a for a in result.areas}
        assert ops["6422927"].op == "update"
        assert "location_name" in ops["6422927"].diff
        assert ops["6422928"].op == "noop"

    @pytest.mark.asyncio
    async def test_property_in_db_but_not_yaml_no_delete_by_default(self):
        # YAML references no properties; DB has one.
        doc = load_yaml_str("properties: []")
        existing = _make_property(id=1, name="Orphan", address="x")
        session = FakeSession(properties=[existing])

        result = await plan(session, doc)
        # No property ops at all because nothing in the YAML and allow_deletes=False
        assert result.properties == []
        assert not result.has_changes

    @pytest.mark.asyncio
    async def test_allow_deletes_emits_delete_ops(self):
        doc = load_yaml_str("properties: []")
        existing = _make_property(
            id=1, name="Orphan", address="x",
            common_areas=[_make_area(id=10, network_id="666", location_name="Old Spot")],
        )
        session = FakeSession(properties=[existing])

        result = await plan(session, doc, allow_deletes=True)
        ops = [p for p in result.properties if p.op == "delete"]
        assert len(ops) == 1 and ops[0].name == "Orphan"
        # The orphan property's areas don't need their own delete ops because
        # cascade handles them when the property is deleted.

    @pytest.mark.asyncio
    async def test_island_default_falls_back_to_property_level(self):
        # The YAML doesn't set island on areas; property has island=oahu.
        # An existing area without island recorded should be flagged as an update.
        doc = load_yaml_str(SAMPLE_YAML)
        existing = _make_property(
            id=1, name="Kapahulu Tower", address="1234 Kapahulu Ave, Honolulu, HI",
            common_areas=[
                _make_area(id=10, network_id="6422927", location_name="Lobby",
                           island=None, location_type=LocationType.INDOOR),
                _make_area(id=11, network_id="6422928", location_name="Pool Deck",
                           island=None, location_type=LocationType.OUTDOOR),
            ],
        )
        session = FakeSession(properties=[existing])

        result = await plan(session, doc)
        ops = {a.network_id: a for a in result.areas}
        # Both should now want the OAHU island
        assert ops["6422927"].op == "update"
        assert ops["6422927"].diff["island"] == (None, "oahu")

    @pytest.mark.asyncio
    async def test_summary_counts_correct(self):
        doc = load_yaml_str(SAMPLE_YAML)
        # Existing has the right property + one matching area + one missing area
        existing = _make_property(
            id=1, name="Kapahulu Tower", address="1234 Kapahulu Ave, Honolulu, HI",
            common_areas=[
                _make_area(id=10, network_id="6422927", location_name="Lobby",
                           island=Island.OAHU, location_type=LocationType.INDOOR),
                # 6422928 missing → should be a create
            ],
        )
        session = FakeSession(properties=[existing])

        result = await plan(session, doc)
        s = result.summary()
        assert s == {
            "properties_create": 0,
            "properties_update": 0,
            "properties_delete": 0,
            "properties_noop": 1,
            "areas_create": 1,
            "areas_update": 0,
            "areas_delete": 0,
            "areas_noop": 1,
        }
