"""Search service.

Mock-mode searches the in-memory fixture; DB-mode does an `ILIKE` across
the relevant text fields. Per-property access is enforced by the caller
(the route already has `get_current_user` + `accessible_property_ids_for`).

The matcher is intentionally simple — a substring match over normalized
text. Operators search by exact substring (property names they remember,
network IDs they're chasing). Fuzzy matching can come later if it earns
its keep.
"""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.common_area import CommonArea
from app.models.property import Property
from app.schemas.search import SearchResult
from app.services.mock_dashboard import _PROPERTIES_RAW
from app.services.mock_property_detail import _NETWORK_NAMES

MAX_RESULTS = 20


def _norm(s: str) -> str:
    return s.lower().strip()


# ──────────────────────────────────────────────────────────────────────────────
# Mock-mode search
# ──────────────────────────────────────────────────────────────────────────────


def search_mock(query: str) -> list[SearchResult]:
    if not query.strip():
        return []
    q = _norm(query)

    out: list[SearchResult] = []

    # Properties
    for p in _PROPERTIES_RAW:
        if q in _norm(p["name"]) or q in _norm(p["co"]):
            out.append(
                SearchResult(
                    kind="property",
                    property_id=p["id"],
                    label=p["name"],
                    sublabel=f"{p['co']} · {p['island']}",
                )
            )

    # Common areas + their synthetic network IDs
    for prop_id, area_names in _NETWORK_NAMES.items():
        prop = next((p for p in _PROPERTIES_RAW if p["id"] == prop_id), None)
        prop_name = prop["name"] if prop else prop_id
        for i, area_name in enumerate(area_names):
            nid = f"{prop_id.upper()}-{i + 1:03d}"
            if q in _norm(area_name):
                out.append(
                    SearchResult(
                        kind="area",
                        property_id=prop_id,
                        label=area_name,
                        sublabel=f"{prop_name} · {nid}",
                        network_id=nid,
                    )
                )
            elif q in _norm(nid):
                out.append(
                    SearchResult(
                        kind="network_id",
                        property_id=prop_id,
                        label=nid,
                        sublabel=f"{prop_name} · {area_name}",
                        network_id=nid,
                    )
                )

    return out[:MAX_RESULTS]


# ──────────────────────────────────────────────────────────────────────────────
# DB-mode search
# ──────────────────────────────────────────────────────────────────────────────


async def search_db(
    session: AsyncSession,
    query: str,
    *,
    accessible_property_ids: set[int] | None = None,
) -> list[SearchResult]:
    """Substring (`ILIKE`) match across the relevant fields. Filters to the
    caller's accessible property set (None means superuser — see all).
    """
    if not query.strip():
        return []

    pattern = f"%{query.strip()}%"
    out: list[SearchResult] = []

    # Properties
    prop_q = select(Property).where(Property.name.ilike(pattern))
    if accessible_property_ids is not None:
        prop_q = prop_q.where(Property.id.in_(accessible_property_ids))
    prop_q = prop_q.order_by(Property.name).limit(MAX_RESULTS)
    for p in (await session.execute(prop_q)).scalars().all():
        out.append(
            SearchResult(
                kind="property",
                property_id=str(p.id),
                label=p.name,
                sublabel=p.address or None,
            )
        )

    # Common areas (joined to Property for the sublabel)
    area_q = (
        select(CommonArea)
        .options(selectinload(CommonArea.property))
        .where(
            or_(
                CommonArea.location_name.ilike(pattern),
                CommonArea.network_name.ilike(pattern),
                CommonArea.network_id.ilike(pattern),
            )
        )
    )
    if accessible_property_ids is not None:
        area_q = area_q.where(CommonArea.property_id.in_(accessible_property_ids))
    area_q = area_q.order_by(CommonArea.location_name).limit(MAX_RESULTS)

    for ca in (await session.execute(area_q)).scalars().all():
        prop_name = ca.property.name if ca.property else "—"
        # Decide kind: if the match is on network_id and not on the human
        # name, surface it as a network_id hit so the icon tells the operator
        # "this is a code, not a place".
        is_id_hit = _norm(query) in _norm(ca.network_id) and _norm(query) not in _norm(ca.location_name)
        if is_id_hit:
            out.append(
                SearchResult(
                    kind="network_id",
                    property_id=str(ca.property_id),
                    label=ca.network_id,
                    sublabel=f"{prop_name} · {ca.location_name}",
                    network_id=ca.network_id,
                )
            )
        else:
            out.append(
                SearchResult(
                    kind="area",
                    property_id=str(ca.property_id),
                    label=ca.location_name,
                    sublabel=f"{prop_name} · {ca.network_id}",
                    network_id=ca.network_id,
                )
            )

    return out[:MAX_RESULTS]
