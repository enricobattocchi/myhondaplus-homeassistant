"""Switch platform for My Honda+."""

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_VEHICLE_NAME, CONF_VIN
from .data import MyHondaPlusConfigEntry
from .entity import MyHondaPlusEntity, to_bool


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
        HondaDefrostSwitch(coordinator, vin, vehicle_name),
        HondaAutoRefreshSwitch(coordinator, vin, vehicle_name, entry),
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
        if isinstance(value, str) and value.lower() == "active":
            return True
        return to_bool(value)

    async def async_turn_on(self, **kwargs) -> None:
        """Start climate pre-conditioning."""
        data = dict(self.coordinator.data)
        prev = data.get("climate_active")
        data["climate_active"] = True
        self.coordinator.async_set_updated_data(data)
        confirmed = await self.coordinator.async_send_command_and_wait(
            self.coordinator.api.remote_climate_start, self._vin,
        )
        if not confirmed:
            data = dict(self.coordinator.data)
            data["climate_active"] = prev
            self.coordinator.async_set_updated_data(data)

    async def async_turn_off(self, **kwargs) -> None:
        """Stop climate pre-conditioning."""
        data = dict(self.coordinator.data)
        prev = data.get("climate_active")
        data["climate_active"] = False
        self.coordinator.async_set_updated_data(data)
        confirmed = await self.coordinator.async_send_command_and_wait(
            self.coordinator.api.remote_climate_stop, self._vin,
        )
        if not confirmed:
            data = dict(self.coordinator.data)
            data["climate_active"] = prev
            self.coordinator.async_set_updated_data(data)


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
            return value.lower() in ("charging", "running")
        return bool(value)

    async def async_turn_on(self, **kwargs) -> None:
        """Start charging."""
        data = dict(self.coordinator.data)
        prev = data.get("charge_status")
        data["charge_status"] = "charging"
        self.coordinator.async_set_updated_data(data)
        confirmed = await self.coordinator.async_send_command_and_wait(
            self.coordinator.api.remote_charge_start, self._vin,
        )
        if not confirmed:
            data = dict(self.coordinator.data)
            data["charge_status"] = prev
            self.coordinator.async_set_updated_data(data)

    async def async_turn_off(self, **kwargs) -> None:
        """Stop charging."""
        data = dict(self.coordinator.data)
        prev = data.get("charge_status")
        data["charge_status"] = "not_charging"
        self.coordinator.async_set_updated_data(data)
        confirmed = await self.coordinator.async_send_command_and_wait(
            self.coordinator.api.remote_charge_stop, self._vin,
        )
        if not confirmed:
            data = dict(self.coordinator.data)
            data["charge_status"] = prev
            self.coordinator.async_set_updated_data(data)


class HondaDefrostSwitch(MyHondaPlusEntity, SwitchEntity):
    """Switch to enable/disable climate defrost setting."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:car-defrost-rear"
    _attr_translation_key = "climate_defrost_setting"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, vin: str, vehicle_name: str) -> None:
        description = SwitchEntityDescription(
            key="climate_defrost_setting",
            translation_key="climate_defrost_setting",
        )
        super().__init__(coordinator, description, vin, vehicle_name)

    @property
    def is_on(self) -> bool:
        """Return true if defrost is enabled."""
        return bool(self.coordinator.data.get("climate_defrost", True))

    async def async_turn_on(self, **kwargs) -> None:
        """Enable defrost."""
        await self._set_defrost(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable defrost."""
        await self._set_defrost(False)

    async def _set_defrost(self, defrost: bool) -> None:
        data = self.coordinator.data or {}
        prev = data.get("climate_defrost")
        temp = data.get("climate_temp", "normal")
        if temp not in ("cooler", "normal", "hotter"):
            temp = "normal"
        duration = data.get("climate_duration", 30)
        if duration not in (10, 20, 30):
            duration = 30
        new_data = dict(self.coordinator.data)
        new_data["climate_defrost"] = defrost
        self.coordinator.async_set_updated_data(new_data)
        confirmed = await self.coordinator.async_send_command_and_wait(
            self.coordinator.api.set_climate_settings,
            self._vin, temp, duration, defrost,
        )
        if not confirmed:
            new_data = dict(self.coordinator.data)
            new_data["climate_defrost"] = prev
            self.coordinator.async_set_updated_data(new_data)


class HondaAutoRefreshSwitch(MyHondaPlusEntity, SwitchEntity):
    """Switch to enable/disable automatic refresh from car."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:refresh-auto"
    _attr_translation_key = "auto_refresh"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, vin: str, vehicle_name: str, entry) -> None:
        description = SwitchEntityDescription(
            key="auto_refresh",
            translation_key="auto_refresh",
        )
        super().__init__(coordinator, description, vin, vehicle_name)
        self._entry = entry

    @property
    def is_on(self) -> bool:
        """Return true if auto refresh is enabled."""
        return self._entry.runtime_data.car_refresh_enabled

    async def async_turn_on(self, **kwargs) -> None:
        """Enable auto refresh."""
        self._entry.runtime_data.car_refresh_enabled = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable auto refresh."""
        self._entry.runtime_data.car_refresh_enabled = False
        self.async_write_ha_state()
