"""Admin endpoints (SPEC §6.1 / §7).

All routes require an authenticated staff or superuser caller.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_staff
from app.core.config import settings
from app.db.session import get_session
from app.models.common_area import CommonArea
from app.models.property import Property
from app.models.user import User
from app.schemas.admin import (
    AreaPreviewRequest,
    AreaPreviewResponse,
    CommonAreaCreate,
    CommonAreaOut,
    CommonAreaUpdate,
    GrantOut,
    GrantRequest,
    PropertyCreate,
    PropertyOut,
    PropertyUpdate,
)
from app.schemas.maintenance import (
    AffectedPropertyOut,
    ClliCreate,
    ClliOut,
    MaintenanceCreate,
    MaintenanceOut,
    MaintenanceUpdate,
)
from app.services import admin as svc
from app.services import maintenance as msvc


async def _refuse_in_mock_mode() -> None:
    """Mock mode has no DB — admin operations are meaningless."""
    if settings.USE_MOCK_DATA:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="admin disabled in mock mode (USE_MOCK_DATA=true)",
        )


router = APIRouter(
    tags=["admin"],
    prefix="/admin",
    dependencies=[Depends(_refuse_in_mock_mode)],
)


# ──────────────────────────────────────────────────────────────────────────────
# Property
# ──────────────────────────────────────────────────────────────────────────────


def _property_out(p: Property, *, common_areas_count: int) -> PropertyOut:
    return PropertyOut(
        id=p.id,
        name=p.name,
        address=p.address,
        created_at=p.created_at,
        updated_at=p.updated_at,
        common_areas_count=common_areas_count,
    )


@router.get("/properties", response_model=list[PropertyOut])
async def list_properties(
    _staff: User = Depends(require_staff),
    session: AsyncSession = Depends(get_session),
) -> list[PropertyOut]:
    rows = (
        await session.execute(
            select(
                Property,
                func.count(CommonArea.id),
            )
            .outerjoin(CommonArea, CommonArea.property_id == Property.id)
            .group_by(Property.id)
            .order_by(Property.name)
        )
    ).all()
    return [_property_out(p, common_areas_count=int(n)) for p, n in rows]


@router.post(
    "/properties",
    response_model=PropertyOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_property(
    payload: PropertyCreate,
    _staff: User = Depends(require_staff),
    session: AsyncSession = Depends(get_session),
) -> PropertyOut:
    p = await svc.create_property(session, payload)
    return _property_out(p, common_areas_count=0)


@router.put("/properties/{property_id}", response_model=PropertyOut)
async def update_property(
    payload: PropertyUpdate,
    property_id: int = Path(..., ge=1),
    _staff: User = Depends(require_staff),
    session: AsyncSession = Depends(get_session),
) -> PropertyOut:
    p = await svc.get_property(session, property_id)
    if p is None:
        raise HTTPException(status_code=404, detail="property not found")
    p = await svc.update_property(session, p, payload)
    n = (
        await session.execute(
            select(func.count(CommonArea.id)).where(CommonArea.property_id == p.id)
        )
    ).scalar_one()
    return _property_out(p, common_areas_count=int(n or 0))


@router.delete("/properties/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(
    property_id: int = Path(..., ge=1),
    _staff: User = Depends(require_staff),
    session: AsyncSession = Depends(get_session),
) -> None:
    p = await svc.get_property(session, property_id)
    if p is None:
        raise HTTPException(status_code=404, detail="property not found")
    await svc.delete_property(session, p)


# ──────────────────────────────────────────────────────────────────────────────
# Common areas
# ──────────────────────────────────────────────────────────────────────────────


def _ca_out(ca: CommonArea) -> CommonAreaOut:
    return CommonAreaOut(
        id=ca.id,
        property_id=ca.property_id,
        location_name=ca.location_name,
        network_id=ca.network_id,
        island=ca.island.value if ca.island else None,  # type: ignore[arg-type]
        location_type=ca.location_type.value,  # type: ignore[arg-type]
        description=ca.description,
        network_name=ca.network_name,
        ssid=ca.ssid,
        wan_ip=ca.wan_ip,
        is_online=ca.is_online,
        last_checked=ca.last_checked,
    )


@router.get("/properties/{property_id}/areas", response_model=list[CommonAreaOut])
async def list_common_areas(
    property_id: int = Path(..., ge=1),
    _staff: User = Depends(require_staff),
    session: AsyncSession = Depends(get_session),
) -> list[CommonAreaOut]:
    p = await svc.get_property(session, property_id)
    if p is None:
        raise HTTPException(status_code=404, detail="property not found")
    rows = (
        await session.execute(
            select(CommonArea)
            .where(CommonArea.property_id == property_id)
            .order_by(CommonArea.location_name)
        )
    ).scalars().all()
    return [_ca_out(ca) for ca in rows]


@router.post(
    "/properties/{property_id}/areas",
    response_model=CommonAreaOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_common_area(
    payload: CommonAreaCreate,
    property_id: int = Path(..., ge=1),
    _staff: User = Depends(require_staff),
    session: AsyncSession = Depends(get_session),
) -> CommonAreaOut:
    p = await svc.get_property(session, property_id)
    if p is None:
        raise HTTPException(status_code=404, detail="property not found")
    ca = await svc.create_common_area(session, p, payload)
    return _ca_out(ca)


@router.put("/areas/{area_id}", response_model=CommonAreaOut)
async def update_common_area(
    payload: CommonAreaUpdate,
    area_id: int = Path(..., ge=1),
    _staff: User = Depends(require_staff),
    session: AsyncSession = Depends(get_session),
) -> CommonAreaOut:
    ca = await svc.get_common_area(session, area_id)
    if ca is None:
        raise HTTPException(status_code=404, detail="area not found")
    ca = await svc.update_common_area(session, ca, payload)
    return _ca_out(ca)


@router.delete("/areas/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_common_area(
    area_id: int = Path(..., ge=1),
    _staff: User = Depends(require_staff),
    session: AsyncSession = Depends(get_session),
) -> None:
    ca = await svc.get_common_area(session, area_id)
    if ca is None:
        raise HTTPException(status_code=404, detail="area not found")
    await svc.delete_common_area(session, ca)


@router.post("/areas/preview", response_model=AreaPreviewResponse)
async def preview_area(
    payload: AreaPreviewRequest,
    _staff: User = Depends(require_staff),
) -> AreaPreviewResponse:
    """SPEC §6.1 — live eero validation. Operator confirms the network_id
    + name + eero count before saving."""
    return await svc.preview_common_area(payload)


# ──────────────────────────────────────────────────────────────────────────────
# Per-property access grants
# ──────────────────────────────────────────────────────────────────────────────


@router.post("/access", response_model=GrantOut, status_code=status.HTTP_201_CREATED)
async def grant_access(
    payload: GrantRequest,
    staff: User = Depends(require_staff),
    session: AsyncSession = Depends(get_session),
) -> GrantOut:
    grant = await svc.grant_property_access(
        session, payload.user_id, payload.property_id, granted_by_user_id=staff.id
    )
    return GrantOut(
        user_id=grant.user_id, property_id=grant.property_id, created_at=grant.created_at
    )


@router.delete("/access", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_access(
    payload: GrantRequest,
    _staff: User = Depends(require_staff),
    session: AsyncSession = Depends(get_session),
) -> None:
    deleted = await svc.revoke_property_access(session, payload.user_id, payload.property_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="grant not found")


# ──────────────────────────────────────────────────────────────────────────────
# CLLI codes (telecom equipment identifiers — SPEC §4.1)
# ──────────────────────────────────────────────────────────────────────────────


def _clli_out(c) -> ClliOut:
    return ClliOut(id=c.id, clli_code=c.clli_code, description=c.description)


@router.get("/clli/olt", response_model=list[ClliOut])
async def list_olt_cllis(
    _staff: User = Depends(require_staff),
    session: AsyncSession = Depends(get_session),
) -> list[ClliOut]:
    rows = await msvc.list_olt_cllis(session)
    return [_clli_out(c) for c in rows]


@router.post("/clli/olt", response_model=ClliOut, status_code=status.HTTP_201_CREATED)
async def create_olt_clli(
    payload: ClliCreate,
    _staff: User = Depends(require_staff),
    session: AsyncSession = Depends(get_session),
) -> ClliOut:
    return _clli_out(await msvc.create_olt_clli(session, payload))


@router.delete("/clli/olt/{clli_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_olt_clli(
    clli_id: int = Path(..., ge=1),
    _staff: User = Depends(require_staff),
    session: AsyncSession = Depends(get_session),
) -> None:
    if not await msvc.delete_olt_clli(session, clli_id):
        raise HTTPException(status_code=404, detail="OLT CLLI not found")


@router.get("/clli/seven-fifty", response_model=list[ClliOut])
async def list_seven_fifty_cllis(
    _staff: User = Depends(require_staff),
    session: AsyncSession = Depends(get_session),
) -> list[ClliOut]:
    rows = await msvc.list_seven_fifty_cllis(session)
    return [_clli_out(c) for c in rows]


@router.post(
    "/clli/seven-fifty", response_model=ClliOut, status_code=status.HTTP_201_CREATED
)
async def create_seven_fifty_clli(
    payload: ClliCreate,
    _staff: User = Depends(require_staff),
    session: AsyncSession = Depends(get_session),
) -> ClliOut:
    return _clli_out(await msvc.create_seven_fifty_clli(session, payload))


@router.delete("/clli/seven-fifty/{clli_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_seven_fifty_clli(
    clli_id: int = Path(..., ge=1),
    _staff: User = Depends(require_staff),
    session: AsyncSession = Depends(get_session),
) -> None:
    if not await msvc.delete_seven_fifty_clli(session, clli_id):
        raise HTTPException(status_code=404, detail="7x50 CLLI not found")


# ──────────────────────────────────────────────────────────────────────────────
# Scheduled maintenance windows (SPEC §4.1, §6.1)
# ──────────────────────────────────────────────────────────────────────────────


async def _maintenance_out(session: AsyncSession, m) -> MaintenanceOut:
    affected = await msvc.get_affected_properties(session, m)
    return MaintenanceOut(
        id=m.id,
        island=m.island.value,  # type: ignore[arg-type]
        scheduled=m.scheduled,
        is_active=m.is_active,
        olt_clli_codes=[c.clli_code for c in m.olt_cllis],
        seven_fifty_clli_codes=[c.clli_code for c in m.seven_fifty_cllis],
        affected_properties=[
            AffectedPropertyOut(id=p.id, name=p.name) for p in affected
        ],
    )


@router.post(
    "/maintenance",
    response_model=MaintenanceOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_maintenance(
    payload: MaintenanceCreate,
    _staff: User = Depends(require_staff),
    session: AsyncSession = Depends(get_session),
) -> MaintenanceOut:
    m = await msvc.create_maintenance(session, payload)
    return await _maintenance_out(session, m)


@router.put("/maintenance/{m_id}", response_model=MaintenanceOut)
async def update_maintenance(
    payload: MaintenanceUpdate,
    m_id: int = Path(..., ge=1),
    _staff: User = Depends(require_staff),
    session: AsyncSession = Depends(get_session),
) -> MaintenanceOut:
    m = await msvc.get_maintenance(session, m_id)
    if m is None:
        raise HTTPException(status_code=404, detail="maintenance not found")
    m = await msvc.update_maintenance(session, m, payload)
    return await _maintenance_out(session, m)


@router.delete("/maintenance/{m_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_maintenance(
    m_id: int = Path(..., ge=1),
    _staff: User = Depends(require_staff),
    session: AsyncSession = Depends(get_session),
) -> None:
    m = await msvc.get_maintenance(session, m_id)
    if m is None:
        raise HTTPException(status_code=404, detail="maintenance not found")
    await msvc.delete_maintenance(session, m)
