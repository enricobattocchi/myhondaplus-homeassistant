"""Base entity for My Honda+."""

from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .coordinator import DashboardData


def to_bool(value) -> bool | None:
    """Convert a value to bool, handling strings from the API."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "on", "yes", "1", "locked")
    return bool(value)


class MyHondaPlusEntity(CoordinatorEntity[DataUpdateCoordinator[DashboardData]]):
    """Base class for My Honda+ entities."""

    _attr_has_entity_name = True
    _refresh_unsub: CALLBACK_TYPE | None = None

    def __init__(
        self,
        coordinator,
        description,
        vin: str,
        vehicle_name: str = "",
        fuel_type: str = "",
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{vin}_{description.key}"
        self._vin = vin
        self._vehicle_name = vehicle_name
        self._fuel_type = fuel_type

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._vin)},
            name=self._vehicle_name or f"Honda {self._vin[-6:]}",
            manufacturer="Honda",
        )

    def _schedule_refresh(self, delay: int = 30) -> None:
        """Schedule a coordinator refresh, replacing any pending one."""
        if self._refresh_unsub:
            self._refresh_unsub()
        self._refresh_unsub = async_call_later(
            self.hass,
            delay,
            self._do_refresh,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cancel pending refresh on removal."""
        if self._refresh_unsub:
            self._refresh_unsub()
            self._refresh_unsub = None
        await super().async_will_remove_from_hass()

    @callback
    def _do_refresh(self, _now) -> None:
        """Trigger coordinator refresh."""
        self._refresh_unsub = None
        self.hass.async_create_task(self.coordinator.async_request_refresh())
