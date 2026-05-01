"""ScheduledMaintenance + association tables (SPEC §4.1)."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.property import OltClli, SevenFiftyClli


class MaintenanceIsland(str, enum.Enum):
    KAUAI = "kauai"
    OAHU = "oahu"
    MOLOKAI = "molokai"
    LANAI = "lanai"
    MAUI = "maui"
    HAWAII = "hawaii"
    ALL = "all"


maintenance_olt_clli = Table(
    "maintenance_olt_clli",
    Base.metadata,
    Column(
        "maintenance_id",
        ForeignKey("scheduled_maintenances.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("olt_clli_id", ForeignKey("olt_cllis.id", ondelete="CASCADE"), primary_key=True),
)

maintenance_seven_fifty_clli = Table(
    "maintenance_seven_fifty_clli",
    Base.metadata,
    Column(
        "maintenance_id",
        ForeignKey("scheduled_maintenances.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "seven_fifty_clli_id",
        ForeignKey("seven_fifty_cllis.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class ScheduledMaintenance(Base, TimestampMixin):
    __tablename__ = "scheduled_maintenances"

    id: Mapped[int] = mapped_column(primary_key=True)
    island: Mapped[MaintenanceIsland] = mapped_column(
        Enum(MaintenanceIsland, name="maintenance_island"), nullable=False
    )
    scheduled: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    olt_cllis: Mapped[list[OltClli]] = relationship(
        secondary=maintenance_olt_clli, back_populates="maintenances"
    )
    seven_fifty_cllis: Mapped[list[SevenFiftyClli]] = relationship(
        secondary=maintenance_seven_fifty_clli, back_populates="maintenances"
    )
