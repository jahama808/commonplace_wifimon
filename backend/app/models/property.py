"""Property + telecom CLLI codes (SPEC §4.1).

Table names use plain snake_case here. When migrating from the existing
Django app, set `__tablename__` to match the dump (e.g. `wifi_property`).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Column, Enum, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._mixins import TimestampMixin
from app.models.common_area import Island

if TYPE_CHECKING:
    from app.models.common_area import CommonArea
    from app.models.maintenance import ScheduledMaintenance


property_olt_clli = Table(
    "property_olt_clli",
    Base.metadata,
    Column("property_id", ForeignKey("properties.id", ondelete="CASCADE"), primary_key=True),
    Column("olt_clli_id", ForeignKey("olt_cllis.id", ondelete="CASCADE"), primary_key=True),
)

property_seven_fifty_clli = Table(
    "property_seven_fifty_clli",
    Base.metadata,
    Column("property_id", ForeignKey("properties.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "seven_fifty_clli_id",
        ForeignKey("seven_fifty_cllis.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Property(Base, TimestampMixin):
    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    island: Mapped[Island | None] = mapped_column(
        Enum(Island, name="island", create_type=False), nullable=True
    )

    common_areas: Mapped[list[CommonArea]] = relationship(
        back_populates="property", cascade="all, delete-orphan"
    )
    olt_cllis: Mapped[list[OltClli]] = relationship(
        secondary=property_olt_clli, back_populates="properties"
    )
    seven_fifty_cllis: Mapped[list[SevenFiftyClli]] = relationship(
        secondary=property_seven_fifty_clli, back_populates="properties"
    )


class OltClli(Base, TimestampMixin):
    __tablename__ = "olt_cllis"

    id: Mapped[int] = mapped_column(primary_key=True)
    clli_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    properties: Mapped[list[Property]] = relationship(
        secondary=property_olt_clli, back_populates="olt_cllis"
    )
    maintenances: Mapped[list[ScheduledMaintenance]] = relationship(
        secondary="maintenance_olt_clli", back_populates="olt_cllis"
    )


class SevenFiftyClli(Base, TimestampMixin):
    __tablename__ = "seven_fifty_cllis"

    id: Mapped[int] = mapped_column(primary_key=True)
    clli_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    properties: Mapped[list[Property]] = relationship(
        secondary=property_seven_fifty_clli, back_populates="seven_fifty_cllis"
    )
    maintenances: Mapped[list[ScheduledMaintenance]] = relationship(
        secondary="maintenance_seven_fifty_clli", back_populates="seven_fifty_cllis"
    )
