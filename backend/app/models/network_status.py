"""NetworkStatus — append-only history of every check (SPEC §4.1)."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.common_area import CommonArea


class NetworkStatus(Base):
    __tablename__ = "network_statuses"
    __table_args__ = (
        Index("ix_network_statuses_checked_at_desc", "checked_at"),
        Index(
            "ix_network_statuses_common_area_checked_at",
            "common_area_id",
            "checked_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    common_area_id: Mapped[int] = mapped_column(
        ForeignKey("common_areas.id", ondelete="CASCADE"), nullable=False
    )
    is_online: Mapped[bool] = mapped_column(Boolean, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    common_area: Mapped[CommonArea] = relationship(back_populates="statuses")
