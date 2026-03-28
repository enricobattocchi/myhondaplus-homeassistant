"""Lock platform for My Honda+."""

from homeassistant.components.lock import LockEntity, LockEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_VEHICLE_NAME, CONF_VIN
from .data import MyHondaPlusConfigEntry
from .entity import MyHondaPlusEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyHondaPlusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up My Honda+ locks."""
    coordinator = entry.runtime_data.coordinator
    vin = entry.data[CONF_VIN]
    vehicle_name = entry.data.get(CONF_VEHICLE_NAME, "")
    async_add_entities([HondaDoorLock(coordinator, vin, vehicle_name)])


class HondaDoorLock(MyHondaPlusEntity, LockEntity):
    """Lock entity for Honda door locks."""

    _attr_translation_key = "doors"

    def __init__(self, coordinator, vin: str, vehicle_name: str) -> None:
        description = LockEntityDescription(
            key="doors",
            translation_key="doors",
        )
        super().__init__(coordinator, description, vin, vehicle_name)

    @property
    def is_locked(self) -> bool | None:
        """Return true if doors are locked."""
        value = self.coordinator.data.get("doors_locked")
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "on", "yes", "1", "locked")
        return bool(value)

    async def async_lock(self, **kwargs) -> None:
        """Lock the doors."""
        confirmed = await self.coordinator.async_send_command_and_wait(
            self.coordinator.api.remote_lock, self._vin,
        )
        if confirmed:
            data = dict(self.coordinator.data)
            data["doors_locked"] = True
            self.coordinator.async_set_updated_data(data)

    async def async_unlock(self, **kwargs) -> None:
        """Unlock the doors."""
        confirmed = await self.coordinator.async_send_command_and_wait(
            self.coordinator.api.remote_unlock, self._vin,
        )
        if confirmed:
            data = dict(self.coordinator.data)
            data["doors_locked"] = False
            self.coordinator.async_set_updated_data(data)
