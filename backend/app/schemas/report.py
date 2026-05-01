"""Request/response shapes for property reports (SPEC §5.7)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ReportRequest(BaseModel):
    """Body of `POST /api/v1/properties/{id}/report`.

    Empty `ssids` means "include all" — same UX as the current Django app
    (zero checkboxes ⇒ all SSIDs).
    """

    ssids: list[str] = Field(default_factory=list)
