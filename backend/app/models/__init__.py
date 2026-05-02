"""Re-export every model so Alembic's autogenerate sees a single import."""
from __future__ import annotations

from app.db.base import Base
from app.models.common_area import CommonArea, Island, LocationType
from app.models.connected_device_count import ConnectedDeviceCount
from app.models.eero_device import EeroDevice
from app.models.maintenance import (
    ScheduledMaintenance,
    maintenance_olt_clli,
    maintenance_seven_fifty_clli,
)
from app.models.mdu_olt_map import MduOltMap
from app.models.network_status import NetworkStatus
from app.models.property import (
    OltClli,
    Property,
    SevenFiftyClli,
    property_olt_clli,
    property_seven_fifty_clli,
)
from app.models.user import User, UserPropertyAccess

__all__ = [
    "Base",
    "CommonArea",
    "ConnectedDeviceCount",
    "EeroDevice",
    "Island",
    "LocationType",
    "MduOltMap",
    "NetworkStatus",
    "OltClli",
    "Property",
    "ScheduledMaintenance",
    "SevenFiftyClli",
    "User",
    "UserPropertyAccess",
    "maintenance_olt_clli",
    "maintenance_seven_fifty_clli",
    "property_olt_clli",
    "property_seven_fifty_clli",
]
