"""Maintenance + CLLI wire shapes (SPEC §4.1, §5.4, §6.1)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

MaintenanceIslandSlug = Literal[
    "all", "oahu", "maui", "big-island", "kauai", "molokai", "lanai", "hawaii"
]


# ──────────────────────────────────────────────────────────────────────────────
# CLLI codes (used by both properties + maintenance)
# ──────────────────────────────────────────────────────────────────────────────


class ClliCreate(BaseModel):
    clli_code: str = Field(min_length=1, max_length=64)
    description: str | None = None


class ClliOut(BaseModel):
    id: int
    clli_code: str
    description: str | None


# ──────────────────────────────────────────────────────────────────────────────
# Scheduled maintenance
# ──────────────────────────────────────────────────────────────────────────────


class MaintenanceCreate(BaseModel):
    island: MaintenanceIslandSlug
    scheduled: datetime
    is_active: bool = True
    olt_clli_codes: list[str] = Field(default_factory=list)
    seven_fifty_clli_codes: list[str] = Field(default_factory=list)


class MaintenanceUpdate(BaseModel):
    island: MaintenanceIslandSlug | None = None
    scheduled: datetime | None = None
    is_active: bool | None = None
    olt_clli_codes: list[str] | None = None
    seven_fifty_clli_codes: list[str] | None = None


class AffectedPropertyOut(BaseModel):
    id: int
    name: str


class MaintenanceOut(BaseModel):
    id: int
    island: MaintenanceIslandSlug
    scheduled: datetime
    is_active: bool
    olt_clli_codes: list[str] = Field(default_factory=list)
    seven_fifty_clli_codes: list[str] = Field(default_factory=list)
    affected_properties: list[AffectedPropertyOut] = Field(default_factory=list)
