"""Search wire shapes (SPEC §5.4 / §8.3 — global search across properties,
common areas, and network IDs)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ResultKind = Literal["property", "area", "network_id"]


class SearchResult(BaseModel):
    kind: ResultKind
    # Stable identifier. For properties this is the Property.id (string).
    # For areas/network_ids this is the parent property id so the FE can
    # open the drawer directly.
    property_id: str
    label: str
    sublabel: str | None = None
    network_id: str | None = None  # populated for `area` and `network_id` kinds


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
