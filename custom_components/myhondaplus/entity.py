"""Base entity for My Honda+."""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONF_FUEL_TYPE, DOMAIN

FUEL_TYPE_LABELS = {
    "E": "Electric",
    "H": "Hybrid",
    "G": "Gasoline",
    "D": "Diesel",
}


class MyHondaPlusEntity(CoordinatorEntity[DataUpdateCoordinator[dict]]):
    """Base class for My Honda+ entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        description,
        vin: str,
        vehicle_name: str = "",
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{vin}_{description.key}"
        self._vin = vin
        self._vehicle_name = vehicle_name
        self._fuel_type = coordinator.entry.data.get(CONF_FUEL_TYPE, "")

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        info = DeviceInfo(
            identifiers={(DOMAIN, self._vin)},
            name=self._vehicle_name or f"Honda {self._vin[-6:]}",
            manufacturer="Honda",
        )
        model = FUEL_TYPE_LABELS.get(self._fuel_type)
        if model:
            info["model"] = model
        return info
