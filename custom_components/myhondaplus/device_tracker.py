"""Device tracker platform for My Honda+."""

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .data import MyHondaPlusConfigEntry
from .entity import MyHondaPlusEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyHondaPlusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up My Honda+ device tracker."""
    async_add_entities(
        HondaDeviceTracker(v.coordinator, v.vin, v.vehicle_name, v.fuel_type)
        for v in entry.runtime_data.vehicles.values()
        if v.capabilities.car_finder
    )


class HondaDeviceTracker(MyHondaPlusEntity, TrackerEntity):
    """Device tracker for Honda vehicle location."""

    _attr_translation_key = "vehicle_location"

    def __init__(
        self, coordinator, vin: str, vehicle_name: str, fuel_type: str = ""
    ) -> None:
        description = EntityDescription(
            key="vehicle_location",
            translation_key="vehicle_location",
        )
        super().__init__(coordinator, description, vin, vehicle_name, fuel_type)

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        val = self.coordinator.data.latitude
        return val if val else None

    @property
    def longitude(self) -> float | None:
        val = self.coordinator.data.longitude
        return val if val else None
