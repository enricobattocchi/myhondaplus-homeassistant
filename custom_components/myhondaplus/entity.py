"""Base entity for My Honda+."""

from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_call_later
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
    _refresh_unsub: CALLBACK_TYPE | None = None

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

    def _schedule_refresh(self, delay: int = 30) -> None:
        """Schedule a coordinator refresh, replacing any pending one."""
        if self._refresh_unsub:
            self._refresh_unsub()
        self._refresh_unsub = async_call_later(
            self.hass, delay, self._do_refresh,
        )

    @callback
    def _do_refresh(self, _now) -> None:
        """Trigger coordinator refresh."""
        self._refresh_unsub = None
        self.hass.async_create_task(self.coordinator.async_request_refresh())
