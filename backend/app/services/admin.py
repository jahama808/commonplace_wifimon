"""Admin service — onboarding flows (SPEC §6.1)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.eero.client import EeroClient
from app.eero.parser import determine_online, extract_device_list, extract_network_metadata
from app.models.common_area import CommonArea, Island, LocationType
from app.models.property import Property
from app.models.user import UserPropertyAccess
from app.schemas.admin import (
    AreaPreviewRequest,
    AreaPreviewResponse,
    CommonAreaCreate,
    CommonAreaUpdate,
    PropertyCreate,
    PropertyUpdate,
)

# ──────────────────────────────────────────────────────────────────────────────
# Property CRUD
# ──────────────────────────────────────────────────────────────────────────────


async def create_property(session: AsyncSession, payload: PropertyCreate) -> Property:
    p = Property(name=payload.name, address=payload.address)
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return p


async def update_property(
    session: AsyncSession, prop: Property, payload: PropertyUpdate
) -> Property:
    if payload.name is not None:
        prop.name = payload.name
    if payload.address is not None:
        prop.address = payload.address
    await session.commit()
    await session.refresh(prop)
    return prop


async def delete_property(session: AsyncSession, prop: Property) -> None:
    await session.delete(prop)
    await session.commit()


async def get_property(session: AsyncSession, property_id: int) -> Property | None:
    return (
        await session.execute(select(Property).where(Property.id == property_id))
    ).scalar_one_or_none()


# ──────────────────────────────────────────────────────────────────────────────
# CommonArea CRUD
# ──────────────────────────────────────────────────────────────────────────────


def _coerce_island(s: str | None) -> Island | None:
    if s is None:
        return None
    # Accept "big-island" wire form for Hawaii
    if s == "big-island":
        return Island.HAWAII
    try:
        return Island(s)
    except ValueError:
        return None


async def create_common_area(
    session: AsyncSession, prop: Property, payload: CommonAreaCreate
) -> CommonArea:
    ca = CommonArea(
        property_id=prop.id,
        location_name=payload.location_name,
        network_id=payload.network_id,
        island=_coerce_island(payload.island),
        location_type=LocationType(payload.location_type),
        description=payload.description,
        api_endpoint=payload.api_endpoint,
    )
    session.add(ca)
    await session.commit()
    await session.refresh(ca)
    return ca


async def update_common_area(
    session: AsyncSession, ca: CommonArea, payload: CommonAreaUpdate
) -> CommonArea:
    if payload.location_name is not None:
        ca.location_name = payload.location_name
    if payload.island is not None:
        ca.island = _coerce_island(payload.island)
    if payload.location_type is not None:
        ca.location_type = LocationType(payload.location_type)
    if payload.description is not None:
        ca.description = payload.description
    if payload.api_endpoint is not None:
        ca.api_endpoint = payload.api_endpoint
    await session.commit()
    await session.refresh(ca)
    return ca


async def delete_common_area(session: AsyncSession, ca: CommonArea) -> None:
    await session.delete(ca)
    await session.commit()


async def get_common_area(session: AsyncSession, area_id: int) -> CommonArea | None:
    return (
        await session.execute(select(CommonArea).where(CommonArea.id == area_id))
    ).scalar_one_or_none()


# ──────────────────────────────────────────────────────────────────────────────
# Eero validation preview (SPEC §6.1)
# ──────────────────────────────────────────────────────────────────────────────


async def preview_common_area(
    payload: AreaPreviewRequest, *, client: EeroClient | None = None
) -> AreaPreviewResponse:
    """Calls the eero API server-side, returns a preview the operator can
    confirm before saving. Always returns a response — failures land in
    the `error` field rather than raising, so the form can render the
    failure inline.
    """
    target = payload.api_endpoint or payload.network_id

    if client is None:
        async with EeroClient() as c:
            return await _do_preview(c, payload.network_id, target)
    return await _do_preview(client, payload.network_id, target)


async def _do_preview(
    client: EeroClient, network_id: str, target: str
) -> AreaPreviewResponse:
    net = await client.get_network(target)
    if not net.ok:
        return AreaPreviewResponse(network_id=network_id, error=net.error_message or "request failed")

    meta = extract_network_metadata(net.payload)
    eeros = await client.get_eeros(target)
    units = extract_device_list(eeros.payload) if eeros.ok else []

    return AreaPreviewResponse(
        network_id=network_id,
        network_name=meta.get("network_name"),
        ssid=meta.get("ssid"),
        wan_ip=meta.get("wan_ip"),
        eero_count=len(units),
        is_online=determine_online(net.payload),
    )


# ──────────────────────────────────────────────────────────────────────────────
# UserPropertyAccess (SPEC §5.1 grant/revoke)
# ──────────────────────────────────────────────────────────────────────────────


async def grant_property_access(
    session: AsyncSession, user_id: int, property_id: int, *, granted_by_user_id: int | None = None
) -> UserPropertyAccess:
    existing = (
        await session.execute(
            select(UserPropertyAccess).where(
                UserPropertyAccess.user_id == user_id,
                UserPropertyAccess.property_id == property_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    grant = UserPropertyAccess(
        user_id=user_id, property_id=property_id, created_by_id=granted_by_user_id
    )
    session.add(grant)
    await session.commit()
    await session.refresh(grant)
    return grant


async def revoke_property_access(
    session: AsyncSession, user_id: int, property_id: int
) -> bool:
    """Returns True if a grant was deleted, False if none existed."""
    grant = (
        await session.execute(
            select(UserPropertyAccess).where(
                UserPropertyAccess.user_id == user_id,
                UserPropertyAccess.property_id == property_id,
            )
        )
    ).scalar_one_or_none()
    if grant is None:
        return False
    await session.delete(grant)
    await session.commit()
    return True
