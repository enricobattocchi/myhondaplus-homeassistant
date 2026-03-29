"""Device tracker platform for My Honda+."""

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_VEHICLE_NAME, CONF_VIN
from .data import MyHondaPlusConfigEntry
from .entity import MyHondaPlusEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyHondaPlusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up My Honda+ device tracker."""
    coordinator = entry.runtime_data.coordinator
    vin = entry.data[CONF_VIN]
    vehicle_name = entry.data.get(CONF_VEHICLE_NAME, "")
    async_add_entities([HondaDeviceTracker(coordinator, vin, vehicle_name)])


def _dms_to_decimal(value) -> float | None:
    """Convert a coordinate value to decimal degrees.

    Handles both decimal strings ("45.123") and DMS strings ("043,33,12.391").
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    parts = value.split(",")
    if len(parts) == 3:
        try:
            degrees = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            return degrees + minutes / 60 + seconds / 3600
        except (ValueError, TypeError):
            return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


class HondaDeviceTracker(MyHondaPlusEntity, TrackerEntity):
    """Device tracker for Honda vehicle location."""

    _attr_translation_key = "vehicle_location"

    def __init__(self, coordinator, vin: str, vehicle_name: str) -> None:
        description = EntityDescription(
            key="vehicle_location",
            translation_key="vehicle_location",
        )
        super().__init__(coordinator, description, vin, vehicle_name)

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        return _dms_to_decimal(self.coordinator.data.get("latitude"))

    @property
    def longitude(self) -> float | None:
        return _dms_to_decimal(self.coordinator.data.get("longitude"))
