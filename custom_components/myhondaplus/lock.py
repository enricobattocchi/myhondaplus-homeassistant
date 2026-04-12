"""Lock platform for My Honda+."""

from dataclasses import replace

from homeassistant.components.lock import LockEntity, LockEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .data import MyHondaPlusConfigEntry
from .entity import MyHondaPlusEntity, to_bool

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyHondaPlusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up My Honda+ locks."""
    async_add_entities(
        HondaDoorLock(v.coordinator, v.vin, v.vehicle_name, v.fuel_type)
        for v in entry.runtime_data.vehicles.values()
        if v.capabilities.remote_lock
    )


class HondaDoorLock(MyHondaPlusEntity, LockEntity):
    """Lock entity for Honda door locks."""

    _attr_translation_key = "doors"

    def __init__(
        self, coordinator, vin: str, vehicle_name: str, fuel_type: str = ""
    ) -> None:
        description = LockEntityDescription(
            key="doors",
            translation_key="doors",
        )
        super().__init__(coordinator, description, vin, vehicle_name, fuel_type)

    @property
    def is_locked(self) -> bool | None:
        """Return true if doors are locked."""
        return to_bool(self.coordinator.data.doors_locked)

    async def async_lock(self, **kwargs) -> None:
        """Lock the doors."""
        self._attr_is_locking = True
        self.async_write_ha_state()
        try:
            confirmed = await self.coordinator.async_send_command_and_wait(
                self.coordinator.api.remote_lock,
                self._vin,
            )
            if confirmed:
                self.coordinator.async_set_updated_data(
                    replace(self.coordinator.data, doors_locked=True)
                )
        finally:
            self._attr_is_locking = False
            self.async_write_ha_state()

    async def async_unlock(self, **kwargs) -> None:
        """Unlock the doors."""
        self._attr_is_unlocking = True
        self.async_write_ha_state()
        try:
            confirmed = await self.coordinator.async_send_command_and_wait(
                self.coordinator.api.remote_unlock,
                self._vin,
            )
            if confirmed:
                self.coordinator.async_set_updated_data(
                    replace(self.coordinator.data, doors_locked=False)
                )
        finally:
            self._attr_is_unlocking = False
            self.async_write_ha_state()
