"""Tests for the pure aggregation helpers — no DB required."""
from __future__ import annotations

import pytest

from app.models.common_area import Island
from app.services.dashboard_aggregation import (
    ISLAND_REGIONS,
    derive_pin,
    island_slug,
    status_rollup,
)


class TestIslandSlug:
    @pytest.mark.parametrize(
        "island,slug",
        [
            (Island.OAHU, "oahu"),
            (Island.MAUI, "maui"),
            (Island.HAWAII, "big-island"),
            (Island.KAUAI, "kauai"),
            (Island.MOLOKAI, "molokai"),
            (Island.LANAI, "lanai"),
        ],
    )
    def test_known_islands(self, island, slug):
        assert island_slug(island) == slug

    def test_none_defaults_to_oahu(self):
        assert island_slug(None) == "oahu"


class TestStatusRollup:
    def test_all_online(self):
        assert status_rollup([True, True, True], [False, False, False]) == ("online", 0)

    def test_all_offline_chronic(self):
        assert status_rollup([False, False], [True, True]) == ("offline", 2)

    def test_some_offline_non_chronic_is_degraded(self):
        # Single area, offline but NOT chronic → "degraded" (Pakalana case)
        assert status_rollup([False], [False]) == ("degraded", 1)

    def test_one_chronic_among_many(self):
        # any chronic-offline → "offline"
        assert status_rollup([True, False, True], [False, True, False]) == ("offline", 1)

    def test_one_non_chronic_offline_among_many(self):
        # offline but never chronic → "degraded"
        assert status_rollup([True, False, True], [False, False, False]) == ("degraded", 1)

    def test_chronic_flag_only_counts_when_offline(self):
        # An online area with a stale is_chronic=true (shouldn't happen in
        # practice but be defensive) doesn't escalate the rollup.
        assert status_rollup([True, True], [True, True]) == ("online", 0)

    def test_empty_input(self):
        assert status_rollup([], []) == ("online", 0)

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            status_rollup([True], [True, False])


class TestDerivePin:
    """The pin must satisfy the actual ellipse constraint that HeroMap
    renders, not just a rectangular bound. The y-radius in normalized
    coords is `r * (W/H * 0.5) ≈ r * 1.184`, NOT `r` — because the
    HeroMap canvas is wider than tall (900 × 380)."""

    def _assert_inside_ellipse(self, slug: str, x: float, y: float) -> None:
        cx, cy, r = ISLAND_REGIONS[slug]
        Y_FACTOR = (900 / 380) * 0.5  # ≈ 1.184
        ellipse_value = ((x - cx) / r) ** 2 + ((y - cy) / (r * Y_FACTOR)) ** 2
        assert ellipse_value <= 1.0, (
            f"{slug}: pin ({x:.4f}, {y:.4f}) outside ellipse "
            f"(center={cx, cy}, r={r}); value={ellipse_value:.4f} > 1"
        )

    def test_pin_lands_inside_island_ellipse(self):
        # Sweep a few synthetic property ids per island.
        for slug in ISLAND_REGIONS:
            for pid in ("aks", "prk", "test-1", "test-2", "x", "yyy", "zz9"):
                x, y = derive_pin(pid, slug)
                self._assert_inside_ellipse(slug, x, y)

    def test_deterministic_for_same_id(self):
        a = derive_pin("aks", "maui")
        b = derive_pin("aks", "maui")
        assert a == b

    def test_different_ids_scatter(self):
        # Spot-check that two arbitrary ids land in different places
        a = derive_pin("aks", "oahu")
        b = derive_pin("prk", "oahu")
        assert a != b

    def test_unknown_slug_falls_back_to_oahu(self):
        x, y = derive_pin("aks", "atlantis")
        self._assert_inside_ellipse("oahu", x, y)
