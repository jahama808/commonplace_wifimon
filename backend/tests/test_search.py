"""Tests for the search service. Mock-mode only — DB-mode covered by
manual smoke tests against a real Postgres."""
from __future__ import annotations

from app.services.search import search_mock


class TestMockSearch:
    def test_empty_query_returns_nothing(self):
        assert search_mock("") == []
        assert search_mock("   ") == []

    def test_property_name_match(self):
        out = search_mock("Park")
        kinds = {(r.kind, r.label) for r in out}
        assert ("property", "Park Lane") in kinds

    def test_property_central_office_match(self):
        out = search_mock("KAILHICO")
        labels = [r.label for r in out if r.kind == "property"]
        assert "Kona Sands" in labels

    def test_common_area_name_match(self):
        out = search_mock("Parking")
        areas = [r for r in out if r.kind == "area"]
        assert any("Parking" in r.label for r in areas)
        # Must carry the parent property id so the FE can open the drawer
        assert all(r.property_id for r in areas)

    def test_network_id_substring_match_kind(self):
        # Synthetic network IDs are uppercase; query is lowercase to make sure
        # the case-insensitive matcher works.
        out = search_mock("prk-002")
        nids = [r for r in out if r.kind == "network_id"]
        assert nids
        assert nids[0].network_id == "PRK-002"
        assert nids[0].property_id == "prk"

    def test_case_insensitive(self):
        a = {(r.kind, r.label) for r in search_mock("PARK")}
        b = {(r.kind, r.label) for r in search_mock("park")}
        assert a == b

    def test_capped_at_max_results(self):
        # "lobby" is a common substring — the mock seeds dozens.
        # Make sure we cap somewhere.
        out = search_mock("lobby")
        assert len(out) <= 20

    def test_results_carry_property_id(self):
        for r in search_mock("Park"):
            assert r.property_id, f"{r} missing property_id"
