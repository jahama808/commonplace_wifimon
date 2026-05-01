"""ConnectedDeviceCount ⭐ — the killer-feature time series (SPEC §3, §4.1).

One sample run writes:
  • exactly ONE "total" row per network (canonical: ssid = "")
  • plus N per-SSID rows per network (one per distinct SSID)

The empty-string SSID convention is what the existing chart layer depends on.
If we ever switch to NULL or a separate `is_total` boolean, the API contract
in `schemas/dashboard.py::DeviceCountsResponse` doesn't have to change — but
this file does.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.common_area import CommonArea


class ConnectedDeviceCount(Base):
    __tablename__ = "connected_device_counts"
    __table_args__ = (
        Index("ix_connected_device_counts_timestamp_desc", "timestamp"),
        Index(
            "ix_connected_device_counts_common_area_timestamp",
            "common_area_id",
            "timestamp",
        ),
        Index("ix_connected_device_counts_ssid_timestamp", "ssid", "timestamp"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    common_area_id: Mapped[int] = mapped_column(
        ForeignKey("common_areas.id", ondelete="CASCADE"), nullable=False
    )
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    ssid: Mapped[str] = mapped_column(String(120), nullable=False, server_default="")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    common_area: Mapped[CommonArea] = relationship(back_populates="device_counts")
