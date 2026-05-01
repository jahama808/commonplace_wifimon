"""Auth wire shapes (SPEC §7)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1, max_length=255)


class CurrentUserResponse(BaseModel):
    id: int
    username: str
    email: str | None = None
    is_active: bool
    is_staff: bool
    is_superuser: bool
    accessible_property_ids: list[int] = Field(default_factory=list)
