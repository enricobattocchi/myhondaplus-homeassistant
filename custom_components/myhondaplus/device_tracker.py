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
        value = self.coordinator.data.get("latitude")
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @property
    def longitude(self) -> float | None:
        value = self.coordinator.data.get("longitude")
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
