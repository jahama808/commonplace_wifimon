"""Pure helpers used by the DB-backed dashboard repo.

Kept in their own module so they're testable without a database.
"""
from __future__ import annotations

import hashlib
import math
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
    # Slug stays "big-island" (legacy URL state + map-region key); user-
    # facing display name is "Hawaii" everywhere.
    "big-island": "Hawaii",
    "kauai": "Kauai",
    "molokai": "Molokai",
    "lanai": "Lanai",
}

# Island ellipse centers + radii in 0..1 SVG-normalized coords. These MUST
# match the values in `frontend/src/components/HeroMap.tsx::ISLAND_CIRCLES`
# — drift causes pins to drift outside their island's silhouette.
#
# HeroMap renders each ellipse with `rx = r * W` and `ry = r * W * 0.5` in
# pixel space (W=900, H=380). `derive_pin` accounts for the y-aspect when
# placing a pin so the result lands inside the rendered ellipse.
#
# Molokai + Lanai don't have rendered silhouettes in the prototype map; we
# park their pins between Oahu and Maui where the actual islands sit.
ISLAND_REGIONS: dict[str, tuple[float, float, float]] = {
    "kauai":      (0.12, 0.32, 0.10),
    "oahu":       (0.32, 0.40, 0.11),
    "molokai":    (0.46, 0.30, 0.05),
    "lanai":      (0.50, 0.42, 0.04),
    "maui":       (0.62, 0.32, 0.12),
    "big-island": (0.82, 0.62, 0.16),
}

# HeroMap canvas viewBox is 900 × 380. The ellipse y-radius in pixels is
# `r * W * 0.5`, so in normalized coords the y-radius is `r * (W/H) * 0.5
# = r * 1.184` — LARGER than the x-radius because the canvas is wider
# than tall.
_HEROMAP_W_OVER_H = 900 / 380  # ≈ 2.368
_PIN_Y_NORM_FACTOR = _HEROMAP_W_OVER_H * 0.5  # ≈ 1.184

# Stay this fraction inside the ellipse boundary so pins never visually
# graze the silhouette. 0.85 = 15% safety margin.
_PIN_SAFETY = 0.85


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
    """Place a pin uniformly at random inside the island's rendered ellipse,
    deterministically seeded by `property_id`. Returns `(lng, lat)` in
    0..1 SVG-normalized coords.

    Same property id + same island always lands in the same spot.
    """
    region = ISLAND_REGIONS.get(island_slug_value, ISLAND_REGIONS["oahu"])
    cx, cy, r = region

    # Two stable samples from the property id: angle ∈ [0, 2π) and
    # radius-fraction ∈ [0, 1) (sqrt for uniform area distribution within
    # the disk — without sqrt, points cluster toward the center).
    digest = hashlib.sha256(str(property_id).encode()).digest()
    angle = (digest[0] / 256) * 2 * math.pi
    radius_fraction = math.sqrt(digest[1] / 256) * _PIN_SAFETY

    dx = r * radius_fraction * math.cos(angle)
    dy = r * _PIN_Y_NORM_FACTOR * radius_fraction * math.sin(angle)
    return cx + dx, cy + dy
