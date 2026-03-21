"""Base entity for My Honda+."""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HondaDataUpdateCoordinator


class MyHondaPlusEntity(CoordinatorEntity[HondaDataUpdateCoordinator]):
    """Base class for My Honda+ entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HondaDataUpdateCoordinator,
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

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._vin)},
            name=self._vehicle_name or f"Honda {self._vin[-6:]}",
            manufacturer="Honda",
        )
