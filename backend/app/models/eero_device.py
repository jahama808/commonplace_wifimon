"""EeroDevice — physical eero unit (SPEC §4.1)."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common_area import LocationType

if TYPE_CHECKING:
    from app.models.common_area import CommonArea


class EeroDevice(Base):
    __tablename__ = "eero_devices"
    __table_args__ = (
        UniqueConstraint("common_area_id", "serial", name="uq_eero_devices_common_area_serial"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    common_area_id: Mapped[int] = mapped_column(
        ForeignKey("common_areas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    serial: Mapped[str] = mapped_column(String(64), nullable=False)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    location_type: Mapped[LocationType] = mapped_column(
        Enum(LocationType, name="location_type", create_type=False),
        nullable=False,
        default=LocationType.INDOOR,
    )
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    firmware_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    is_online: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    offline_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_chronic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    last_notification_sent: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    common_area: Mapped[CommonArea] = relationship(back_populates="eero_devices")
