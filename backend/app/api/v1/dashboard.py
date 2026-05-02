"""Dashboard endpoints (SPEC §7).

Reads pick mock vs DB-backed at request time based on `USE_MOCK_DATA`.
The wire shape is identical either way.

Auth (SPEC §5.1): all endpoints require an authenticated session.
Property-scoped endpoints additionally enforce per-property access.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_session
from app.models.user import User
from app.schemas.area_detail import AreaDetailResponse
from app.schemas.dashboard import DashboardResponse, DeviceCountsResponse
from app.schemas.property_detail import PropertyDetailResponse
from app.schemas.report import ReportRequest
from app.schemas.search import SearchResponse
from app.services.area_detail_db import build_area_detail_db
from app.services.auth import accessible_property_ids_for
from app.services.dashboard_db import build_dashboard_db
from app.services.dashboard_stream import db_event_stream, mock_event_stream
from app.services.device_counts_db import (
    device_counts_for_property,
    ssids_for_property,
)
from app.services.mock_area_detail import build_area_detail
from app.services.mock_dashboard import AVAILABLE_SSIDS, _hero_chart, build_dashboard
from app.services.mock_property_detail import build_property_detail
from app.services.property_detail_db import build_property_detail_db
from app.services.report_builder import generate_property_report
from app.services.search import search_db, search_mock

router = APIRouter(tags=["dashboard"])


@router.get(
    "/maintenance",
    summary="Active future scheduled maintenance windows + affected properties",
)
async def get_maintenance(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list:
    """SPEC §5.4 — feeds the dashboard's "Scheduled Maintenance" card."""
    if settings.USE_MOCK_DATA:
        from app.services.mock_dashboard import _mock_maintenance

        return [m.model_dump() for m in _mock_maintenance()]

    from app.services.dashboard_db import _maintenance_windows

    return [m.model_dump() for m in await _maintenance_windows(session)]


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Global search across properties, common areas, and network IDs",
)
async def get_search(
    q: str = Query(default=""),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SearchResponse:
    """SPEC §5.4 / §8.3 — global search bar in the header / Cmd+K palette."""
    if settings.USE_MOCK_DATA:
        results = search_mock(q)
    else:
        accessible = await accessible_property_ids_for(session, user)
        # Superuser → no filter; others → restrict to their accessible set
        scope = None if user.is_superuser else accessible
        results = await search_db(session, q, accessible_property_ids=scope)
    return SearchResponse(query=q, results=results)


@router.get(
    "/dashboard/stream",
    summary="Server-Sent Events stream of dashboard invalidations (SPEC §5.4)",
)
async def get_dashboard_stream(
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Long-lived SSE connection. Emits:

      • `hello`              — handshake on connect
      • `dashboard.invalidate` — client should re-fetch `/api/v1/dashboard`
      • `:heartbeat` comments  — keep-alives so proxies don't time out

    Falls back to 30s polling on the client if the connection drops.
    """
    if settings.USE_MOCK_DATA:
        gen = mock_event_stream()
    else:
        # Build a session factory that doesn't depend on FastAPI's request scope
        # so the generator can keep running across the life of the connection.
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from app.db.session import get_engine

        sm = async_sessionmaker(get_engine(), expire_on_commit=False)
        gen = db_event_stream(sm)

    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    island: str | None = Query(default=None),
    days: int = Query(default=7, ge=1, le=30),
    ssid: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    """Per-user filtered dashboard.

    Mock path returns the full set (dev convenience). Real path filters
    properties to those the caller has access to.
    """
    from app.api.metrics import DASHBOARD_REQUESTS

    if settings.USE_MOCK_DATA:
        DASHBOARD_REQUESTS.labels(mode="mock").inc()
        return build_dashboard(island_filter=island, days=days, ssid=ssid)

    DASHBOARD_REQUESTS.labels(mode="db").inc()
    accessible = await accessible_property_ids_for(session, user)
    payload = await build_dashboard_db(
        session, island_filter=island, days=days, ssid=ssid
    )
    payload.properties = [p for p in payload.properties if int(p.id) in accessible]
    payload.total_properties = len(payload.properties)
    return payload


@router.get(
    "/properties/{property_id}/device-counts",
    response_model=DeviceCountsResponse,
    summary="Connected-devices time series for stacked-area chart",
)
async def get_device_counts(
    property_id: str = Path(...),
    days: int = Query(default=1, ge=1, le=30),
    ssid: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DeviceCountsResponse:
    """Critical, must-retain feature (SPEC §3 / README backend contract).

    `ssid` omitted → totals (canonical `ssid=""` rows in `connected_device_count`).
    `ssid` present → filtered series. Same timestamps drive both views.
    """
    if settings.USE_MOCK_DATA:
        payload = _hero_chart(days=days)
        if ssid:
            payload = payload.model_copy(update={"ssid": ssid})
        return payload

    if not property_id.isdigit():
        raise HTTPException(status_code=404, detail="property not found")
    accessible = await accessible_property_ids_for(session, user)
    pid = int(property_id)
    if pid not in accessible:
        raise HTTPException(status_code=403, detail="no access to this property")
    return await device_counts_for_property(session, pid, days=days, ssid=ssid)


@router.get(
    "/properties/{property_id}/ssids",
    response_model=list[str],
    summary="Distinct SSIDs seen for this property in the window",
)
async def get_property_ssids(
    property_id: str = Path(...),
    days: int = Query(default=7, ge=1, le=30),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[str]:
    """SPEC §7 — feeds the SSID dropdown on the Property Detail page."""
    if settings.USE_MOCK_DATA:
        return list(AVAILABLE_SSIDS)
    if not property_id.isdigit():
        raise HTTPException(status_code=404, detail="property not found")
    accessible = await accessible_property_ids_for(session, user)
    pid = int(property_id)
    if pid not in accessible:
        raise HTTPException(status_code=403, detail="no access to this property")
    return await ssids_for_property(session, pid, days=days)


@router.get(
    "/properties/{property_id}",
    response_model=PropertyDetailResponse,
    summary="Property detail (drives the dashboard drawer)",
)
async def get_property(
    property_id: str = Path(...),
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PropertyDetailResponse:
    """Property detail.

    Mock path uses string IDs ("aks", "prk", …) so we can't pre-validate
    via `require_property_access` (which expects int). The DB path enforces
    per-property access inline.
    """
    if settings.USE_MOCK_DATA:
        detail = build_property_detail(property_id)
    else:
        if not property_id.isdigit():
            raise HTTPException(status_code=404, detail="property not found")
        accessible = await accessible_property_ids_for(session, _user)
        if int(property_id) not in accessible:
            raise HTTPException(status_code=403, detail="no access to this property")
        detail = await build_property_detail_db(session, property_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="property not found")
    return detail


@router.post(
    "/properties/{property_id}/report",
    summary="Generate a PDF WiFi network report for the property (SPEC §5.7)",
)
async def post_property_report(
    payload: ReportRequest,
    property_id: str = Path(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """`POST /api/v1/properties/{id}/report` `{ssids: [...]}` → streams PDF.

    Empty `ssids` means "include all" (matches the current Django app).
    """
    # Per-property access enforcement
    if not settings.USE_MOCK_DATA:
        if not property_id.isdigit():
            raise HTTPException(status_code=404, detail="property not found")
        accessible = await accessible_property_ids_for(session, user)
        if int(property_id) not in accessible:
            raise HTTPException(status_code=403, detail="no access to this property")

    try:
        pdf_bytes, filename = await generate_property_report(
            session, property_id=property_id, ssids=payload.ssids
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/areas/{area_id}",
    response_model=AreaDetailResponse,
    summary="Common-area detail (SPEC §5.6)",
)
async def get_area(
    area_id: str = Path(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AreaDetailResponse:
    """`area_id` is the network_id (e.g. `AKS-001`). Mock-mode short-circuits;
    real-mode enforces per-property access via the parent property."""
    if settings.USE_MOCK_DATA:
        detail = build_area_detail(area_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="area not found")
        return detail

    detail = await build_area_detail_db(session, area_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="area not found")
    accessible = await accessible_property_ids_for(session, user)
    if int(detail.property_id) not in accessible:
        raise HTTPException(status_code=403, detail="no access to this area")
    return detail
