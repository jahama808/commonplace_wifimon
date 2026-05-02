"""CommonArea — one WiFi network at a property (SPEC §4.1)."""
from __future__ import annotations

import enum
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.connected_device_count import ConnectedDeviceCount
    from app.models.eero_device import EeroDevice
    from app.models.network_status import NetworkStatus
    from app.models.property import Property


class Island(str, enum.Enum):
    KAUAI = "kauai"
    OAHU = "oahu"
    MOLOKAI = "molokai"
    LANAI = "lanai"
    MAUI = "maui"
    HAWAII = "hawaii"


class LocationType(str, enum.Enum):
    INDOOR = "indoor"
    OUTDOOR = "outdoor"


class CommonArea(Base, TimestampMixin):
    __tablename__ = "common_areas"
    __table_args__ = (
        UniqueConstraint("property_id", "location_name", name="uq_common_areas_property_location"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    property_id: Mapped[int] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True
    )

    island: Mapped[Island | None] = mapped_column(Enum(Island, name="island"), nullable=True)
    location_type: Mapped[LocationType] = mapped_column(
        Enum(LocationType, name="location_type"),
        nullable=False,
        default=LocationType.INDOOR,
        # SQLAlchemy stores Enum members by `.name` (uppercase) in the
        # Postgres ENUM, so the server-side default must match — using
        # `.value` ("indoor") would error at INSERT time.
        server_default=LocationType.INDOOR.name,
    )
    location_name: Mapped[str] = mapped_column(String(120), nullable=False)
    network_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_endpoint: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Auto-populated from the eero API response
    network_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ssid: Mapped[str | None] = mapped_column(String(120), nullable=True)
    wan_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # Cached current status
    is_online: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    offline_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_chronic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    property: Mapped[Property] = relationship(back_populates="common_areas")
    statuses: Mapped[list[NetworkStatus]] = relationship(
        back_populates="common_area", cascade="all, delete-orphan"
    )
    eero_devices: Mapped[list[EeroDevice]] = relationship(
        back_populates="common_area", cascade="all, delete-orphan"
    )
    device_counts: Mapped[list[ConnectedDeviceCount]] = relationship(
        back_populates="common_area", cascade="all, delete-orphan"
    )

    def can_check_status(self, *, now: datetime | None = None) -> bool:
        """SPEC §5.2 — per-network 1-hour rate limit (admin force-check bypasses)."""
        if self.last_checked is None:
            return True
        ref = now or datetime.now(tz=UTC)
        return ref - self.last_checked > timedelta(hours=1)
