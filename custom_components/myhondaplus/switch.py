"""Switch platform for My Honda+."""

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity, SwitchEntityDescription
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
    """Set up My Honda+ switches."""
    coordinator = entry.runtime_data.coordinator
    vin = entry.data[CONF_VIN]
    vehicle_name = entry.data.get(CONF_VEHICLE_NAME, "")
    async_add_entities([
        HondaClimateSwitch(coordinator, vin, vehicle_name),
        HondaChargeSwitch(coordinator, vin, vehicle_name),
    ])


class HondaClimateSwitch(MyHondaPlusEntity, SwitchEntity):
    """Switch to start/stop climate pre-conditioning."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:air-conditioner"
    _attr_translation_key = "climate"

    def __init__(self, coordinator, vin: str, vehicle_name: str) -> None:
        description = SwitchEntityDescription(
            key="climate",
            translation_key="climate",
        )
        super().__init__(coordinator, description, vin, vehicle_name)

    @property
    def is_on(self) -> bool | None:
        """Return true if climate is active."""
        value = self.coordinator.data.get("climate_active")
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "on", "yes", "1", "active")
        return bool(value)

    async def async_turn_on(self, **kwargs) -> None:
        """Start climate pre-conditioning."""
        api = self.coordinator.api
        await self.coordinator.async_send_command(api.remote_climate_start, self._vin)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Stop climate pre-conditioning."""
        api = self.coordinator.api
        await self.coordinator.async_send_command(api.remote_climate_stop, self._vin)
        self.async_write_ha_state()


class HondaChargeSwitch(MyHondaPlusEntity, SwitchEntity):
    """Switch to start/stop charging."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:ev-station"
    _attr_translation_key = "charging"

    def __init__(self, coordinator, vin: str, vehicle_name: str) -> None:
        description = SwitchEntityDescription(
            key="charging",
            translation_key="charging",
        )
        super().__init__(coordinator, description, vin, vehicle_name)

    @property
    def is_on(self) -> bool | None:
        """Return true if charging is active."""
        value = self.coordinator.data.get("charge_status")
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("charging",)
        return bool(value)

    async def async_turn_on(self, **kwargs) -> None:
        """Start charging."""
        api = self.coordinator.api
        await self.coordinator.async_send_command(api.remote_charge_start, self._vin)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Stop charging."""
        api = self.coordinator.api
        await self.coordinator.async_send_command(api.remote_charge_stop, self._vin)
        self.async_write_ha_state()
