"""Admin wire shapes (SPEC §6.1, §7).

CRUD for Property and CommonArea, plus the live eero validation preview.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Island = Literal["oahu", "maui", "big-island", "kauai", "molokai", "lanai", "hawaii"]
LocationType = Literal["indoor", "outdoor"]


# ──────────────────────────────────────────────────────────────────────────────
# Property
# ──────────────────────────────────────────────────────────────────────────────


class PropertyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    address: str | None = None


class PropertyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    address: str | None = None


class PropertyOut(BaseModel):
    id: int
    name: str
    address: str | None
    created_at: datetime
    updated_at: datetime
    common_areas_count: int = 0


# ──────────────────────────────────────────────────────────────────────────────
# CommonArea
# ──────────────────────────────────────────────────────────────────────────────


class CommonAreaCreate(BaseModel):
    location_name: str = Field(min_length=1, max_length=120)
    network_id: str = Field(min_length=1, max_length=64)
    island: Island | None = None
    location_type: LocationType = "indoor"
    description: str | None = None
    api_endpoint: str | None = None


class CommonAreaUpdate(BaseModel):
    location_name: str | None = Field(default=None, min_length=1, max_length=120)
    island: Island | None = None
    location_type: LocationType | None = None
    description: str | None = None
    api_endpoint: str | None = None


class CommonAreaOut(BaseModel):
    id: int
    property_id: int
    location_name: str
    network_id: str
    island: Island | None
    location_type: LocationType
    description: str | None
    network_name: str | None
    ssid: str | None
    wan_ip: str | None
    is_online: bool
    last_checked: datetime | None


# ──────────────────────────────────────────────────────────────────────────────
# Eero live validation (SPEC §6.1: "real-time" via /admin/areas/preview)
# ──────────────────────────────────────────────────────────────────────────────


class AreaPreviewRequest(BaseModel):
    network_id: str = Field(min_length=1, max_length=64)
    api_endpoint: str | None = None


class AreaPreviewResponse(BaseModel):
    """Returned by `POST /api/v1/admin/areas/preview`.

    Lets the operator confirm a `network_id` actually exists and belongs to
    the right network before saving. The number of eero units is what they
    use as a sanity check.
    """

    network_id: str
    network_name: str | None = None
    ssid: str | None = None
    wan_ip: str | None = None
    eero_count: int = 0
    is_online: bool = False
    error: str | None = None


# ──────────────────────────────────────────────────────────────────────────────
# UserPropertyAccess
# ──────────────────────────────────────────────────────────────────────────────


class GrantRequest(BaseModel):
    user_id: int
    property_id: int


class GrantOut(BaseModel):
    user_id: int
    property_id: int
    created_at: datetime


# ──────────────────────────────────────────────────────────────────────────────
# MDU↔OLT map
# ──────────────────────────────────────────────────────────────────────────────


class MduOltMapOut(BaseModel):
    id: int
    mdu_name: str
    fdh_name: str | None = None
    equip_name: str | None = None
    serving_olt: str | None = None
    equip_name_1: str | None = None
    equip_model: str | None = None


class MduOltMapUploadResponse(BaseModel):
    rows_imported: int
    distinct_mdus: int
