"""Tests for `compute_affected_property_ids` (SPEC §11 checklist item).

Covers every interesting case of the property↔maintenance CLLI overlap
without needing a DB session.
"""
from __future__ import annotations

from app.services.maintenance import compute_affected_property_ids


class TestComputeAffectedPropertyIds:
    def test_empty_inputs_returns_empty(self):
        assert (
            compute_affected_property_ids(
                island="oahu",
                olt_codes=set(),
                seven_fifty_codes=set(),
                properties_olt={},
                properties_seven_fifty={},
            )
            == set()
        )

    def test_single_olt_match(self):
        # One property has an OLT CLLI that intersects with the maintenance.
        affected = compute_affected_property_ids(
            island="oahu",
            olt_codes={"HNLLHIXAOLT01"},
            seven_fifty_codes=set(),
            properties_olt={1: {"HNLLHIXAOLT01"}, 2: {"OTHEROLT01"}},
            properties_seven_fifty={},
        )
        assert affected == {1}

    def test_seven_fifty_match(self):
        affected = compute_affected_property_ids(
            island="oahu",
            olt_codes=set(),
            seven_fifty_codes={"HNL750"},
            properties_olt={},
            properties_seven_fifty={1: {"HNL750"}, 2: {"OTHER750"}},
        )
        assert affected == {1}

    def test_either_clli_type_counts(self):
        # Property has an OLT match; maintenance specifies both kinds.
        affected = compute_affected_property_ids(
            island="oahu",
            olt_codes={"OLT-A"},
            seven_fifty_codes={"750-X"},
            properties_olt={1: {"OLT-A"}, 2: set()},
            properties_seven_fifty={1: set(), 2: {"OTHER750"}},
        )
        assert affected == {1}

    def test_multi_clli_intersection(self):
        # Maintenance spans multiple CLLIs — properties that touch any of
        # them should be flagged (set intersection).
        affected = compute_affected_property_ids(
            island="oahu",
            olt_codes={"OLT-A", "OLT-B", "OLT-C"},
            seven_fifty_codes=set(),
            properties_olt={
                1: {"OLT-A"},        # match
                2: {"OLT-X"},        # miss
                3: {"OLT-C", "OLT-Z"},  # match (intersection on C)
                4: set(),            # miss
            },
            properties_seven_fifty={},
        )
        assert affected == {1, 3}

    def test_no_intersection_returns_empty(self):
        affected = compute_affected_property_ids(
            island="oahu",
            olt_codes={"OLT-NONE"},
            seven_fifty_codes={"750-NONE"},
            properties_olt={1: {"OLT-A"}, 2: {"OLT-B"}},
            properties_seven_fifty={1: {"750-X"}, 2: {"750-Y"}},
        )
        assert affected == set()

    def test_island_all_with_no_clli_codes_flags_everything_known(self):
        # `island="all"` AND no CLLI codes → fleetwide event with no
        # equipment hooks. SPEC §4.1 — return every known property.
        affected = compute_affected_property_ids(
            island="all",
            olt_codes=set(),
            seven_fifty_codes=set(),
            properties_olt={1: {"OLT-A"}, 2: set()},
            properties_seven_fifty={3: {"750-X"}},
        )
        # Union of property ids in either map
        assert affected == {1, 2, 3}

    def test_island_specific_with_no_clli_codes_flags_nothing(self):
        # No CLLI hooks, no fleetwide flag → nothing matches.
        affected = compute_affected_property_ids(
            island="oahu",
            olt_codes=set(),
            seven_fifty_codes=set(),
            properties_olt={1: {"OLT-A"}},
            properties_seven_fifty={},
        )
        assert affected == set()

    def test_island_all_with_clli_still_uses_intersection(self):
        # `island="all"` is a hint, not a license to flag everything when
        # specific CLLIs ARE provided.
        affected = compute_affected_property_ids(
            island="all",
            olt_codes={"OLT-A"},
            seven_fifty_codes=set(),
            properties_olt={1: {"OLT-A"}, 2: {"OTHER"}, 3: set()},
            properties_seven_fifty={},
        )
        assert affected == {1}

    def test_property_present_in_one_map_only(self):
        # If a property has no OLT CLLIs but does have 7x50s (or vice versa),
        # it should still be considered for matching.
        affected = compute_affected_property_ids(
            island="oahu",
            olt_codes=set(),
            seven_fifty_codes={"750-X"},
            properties_olt={1: {"OLT-A"}},
            properties_seven_fifty={2: {"750-X"}},
        )
        assert affected == {2}
