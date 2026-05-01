"""Pydantic schemas for the `wifimon import` YAML format (SPEC §6.1)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Island = Literal["oahu", "maui", "big-island", "kauai", "molokai", "lanai", "hawaii"]
LocationType = Literal["indoor", "outdoor"]


class CommonAreaSpec(BaseModel):
    location_name: str = Field(min_length=1, max_length=120)
    network_id: str = Field(min_length=1, max_length=64)
    location_type: LocationType = "indoor"
    island: Island | None = None  # falls back to property-level island
    description: str | None = None
    api_endpoint: str | None = None


class PropertySpec(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    address: str | None = None
    island: Island | None = None  # default for child common areas
    olt_cllis: list[str] = Field(default_factory=list)
    seven_fifty_cllis: list[str] = Field(default_factory=list)
    common_areas: list[CommonAreaSpec] = Field(default_factory=list)


class ImportFile(BaseModel):
    properties: list[PropertySpec] = Field(default_factory=list)
