"""MduOltMap — uploaded MDU↔OLT spreadsheet rows.

One spreadsheet row per (MDU, OLT) pair. A single MDU can appear multiple
times (different OLTs / 7x50 redundancy). Lookups are by `mdu_name`, which
the upload service derives from the source SAG column by stripping
asterisks and prefix junk.
"""
from __future__ import annotations

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._mixins import TimestampMixin


class MduOltMap(Base, TimestampMixin):
    __tablename__ = "mdu_olt_map"
    __table_args__ = (
        # Re-uploads should idempotently dedupe on the natural key. Different
        # OLT/7x50 pairings are distinct rows.
        UniqueConstraint(
            "mdu_name",
            "equip_name",
            "equip_name_1",
            name="uq_mdu_olt_map_natural",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    mdu_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    fdh_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    equip_name: Mapped[str | None] = mapped_column(String(64), nullable=True)  # OLT CLLI
    serving_olt: Mapped[str | None] = mapped_column(String(64), nullable=True)  # OLT type
    equip_name_1: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 7x50
    equip_model: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 7x50 model
