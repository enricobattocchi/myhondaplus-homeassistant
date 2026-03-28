"""Select platform for My Honda+."""

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_VEHICLE_NAME, CONF_VIN
from .data import MyHondaPlusConfigEntry
from .entity import MyHondaPlusEntity

CLIMATE_TEMP_OPTIONS = ["cooler", "normal", "hotter"]
CLIMATE_DURATION_OPTIONS = ["10", "20", "30"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyHondaPlusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up My Honda+ select entities."""
    coordinator = entry.runtime_data.coordinator
    vin = entry.data[CONF_VIN]
    vehicle_name = entry.data.get(CONF_VEHICLE_NAME, "")
    async_add_entities([
        HondaClimateTempSelect(coordinator, vin, vehicle_name),
        HondaClimateDurationSelect(coordinator, vin, vehicle_name),
    ])


class HondaClimateTempSelect(MyHondaPlusEntity, SelectEntity):
    """Select entity for climate temperature setting."""

    _attr_icon = "mdi:thermometer"
    _attr_translation_key = "climate_temp_setting"
    _attr_options = CLIMATE_TEMP_OPTIONS

    def __init__(self, coordinator, vin: str, vehicle_name: str) -> None:
        description = SelectEntityDescription(
            key="climate_temp_setting",
            translation_key="climate_temp_setting",
        )
        super().__init__(coordinator, description, vin, vehicle_name)

    @property
    def current_option(self) -> str | None:
        value = self.coordinator.data.get("climate_temp")
        if value in CLIMATE_TEMP_OPTIONS:
            return value
        return "normal"

    async def async_select_option(self, option: str) -> None:
        """Update climate temperature setting on the vehicle."""
        data = self.coordinator.data or {}
        duration = data.get("climate_duration", 30)
        if duration not in (10, 20, 30):
            duration = 30
        defrost = data.get("climate_defrost", True)
        confirmed = await self.coordinator.async_send_command_and_wait(
            self.coordinator.api.set_climate_settings,
            self._vin, option, duration, defrost,
        )
        if confirmed:
            new_data = dict(self.coordinator.data)
            new_data["climate_temp"] = option
            self.coordinator.async_set_updated_data(new_data)


class HondaClimateDurationSelect(MyHondaPlusEntity, SelectEntity):
    """Select entity for climate duration setting."""

    _attr_icon = "mdi:timer-outline"
    _attr_translation_key = "climate_duration_setting"
    _attr_options = CLIMATE_DURATION_OPTIONS

    def __init__(self, coordinator, vin: str, vehicle_name: str) -> None:
        description = SelectEntityDescription(
            key="climate_duration_setting",
            translation_key="climate_duration_setting",
        )
        super().__init__(coordinator, description, vin, vehicle_name)

    @property
    def current_option(self) -> str | None:
        value = self.coordinator.data.get("climate_duration")
        if value in (10, 20, 30):
            return str(value)
        return "30"

    async def async_select_option(self, option: str) -> None:
        """Update climate duration setting on the vehicle."""
        data = self.coordinator.data or {}
        temp = data.get("climate_temp", "normal")
        if temp not in CLIMATE_TEMP_OPTIONS:
            temp = "normal"
        defrost = data.get("climate_defrost", True)
        duration = int(option)
        confirmed = await self.coordinator.async_send_command_and_wait(
            self.coordinator.api.set_climate_settings,
            self._vin, temp, duration, defrost,
        )
        if confirmed:
            new_data = dict(self.coordinator.data)
            new_data["climate_duration"] = duration
            self.coordinator.async_set_updated_data(new_data)
