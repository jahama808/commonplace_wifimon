"""Pure helpers used by the DB-backed dashboard repo.

Kept in their own module so they're testable without a database.
"""
from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Literal

from app.models.common_area import Island

Status = Literal["online", "degraded", "offline"]

# Wire-shape island slugs (kebab-case, matches the frontend `Island` type).
ISLAND_SLUG: dict[Island, str] = {
    Island.OAHU: "oahu",
    Island.MAUI: "maui",
    Island.HAWAII: "big-island",  # design / wire convention
    Island.KAUAI: "kauai",
    Island.MOLOKAI: "molokai",
    Island.LANAI: "lanai",
}

ISLAND_LABEL: dict[str, str] = {
    "oahu": "Oahu",
    "maui": "Maui",
    "big-island": "Big Island",
    "kauai": "Kauai",
    "molokai": "Molokai",
    "lanai": "Lanai",
}

# Region centers + scatter radius for the stylized HeroMap (0..1 normalized
# SVG coords). These are visual placement, NOT geographic coordinates.
ISLAND_REGIONS: dict[str, tuple[float, float, float]] = {
    "kauai":      (0.18, 0.30, 0.04),
    "oahu":       (0.32, 0.42, 0.06),
    "molokai":    (0.45, 0.30, 0.04),
    "lanai":      (0.50, 0.36, 0.03),
    "maui":       (0.62, 0.32, 0.06),
    "big-island": (0.82, 0.62, 0.08),
}


def island_slug(island: Island | None) -> str:
    if island is None:
        return "oahu"  # safe default for unset
    return ISLAND_SLUG[island]


def status_rollup(
    online_flags: Iterable[bool], chronic_flags: Iterable[bool]
) -> tuple[Status, int]:
    """Roll a property's status up from its CommonAreas.

    Returns `(status, offline_count)`.

    Rules:
      • offline_count = number of areas with is_online=false
      • any chronic-offline area → "offline"
      • any non-chronic offline area → "degraded"
      • else → "online"
    """
    online = list(online_flags)
    chronic = list(chronic_flags)
    if len(online) != len(chronic):
        raise ValueError("online_flags and chronic_flags must have equal length")

    offline_count = sum(1 for v in online if not v)
    if offline_count == 0:
        return "online", 0
    has_chronic = any(c for c, o in zip(chronic, online, strict=True) if not o)
    return ("offline" if has_chronic else "degraded"), offline_count


def derive_pin(property_id: int | str, island_slug_value: str) -> tuple[float, float]:
    """Place a property pin inside its island's region with a deterministic
    scatter so the same property always lands in the same spot.

    Returns `(lng, lat)` in 0..1 SVG-normalized coords.
    """
    region = ISLAND_REGIONS.get(island_slug_value, ISLAND_REGIONS["oahu"])
    cx, cy, r = region

    # Two stable [-1, 1] samples from the property id
    digest = hashlib.sha256(str(property_id).encode()).digest()
    dx = (digest[0] / 255 - 0.5) * 2  # [-1, 1]
    dy = (digest[1] / 255 - 0.5) * 2
    return cx + dx * r, cy + dy * r * 0.6  # squashed vertically to feel island-shaped
