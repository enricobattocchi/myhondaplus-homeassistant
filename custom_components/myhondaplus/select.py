"""Select platform for My Honda+."""

from dataclasses import replace

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .data import MyHondaPlusConfigEntry
from .entity import MyHondaPlusEntity

PARALLEL_UPDATES = 1

CLIMATE_TEMP_OPTIONS = ["cooler", "normal", "hotter"]
CLIMATE_DURATION_OPTIONS = ["10", "20", "30"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyHondaPlusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up My Honda+ select entities."""
    entities = []
    for v in entry.runtime_data.vehicles.values():
        if v.capabilities.remote_climate and not v.ui_config.hide_climate_settings:
            entities.extend(
                [
                    HondaClimateTempSelect(
                        v.coordinator, v.vin, v.vehicle_name, v.fuel_type
                    ),
                    HondaClimateDurationSelect(
                        v.coordinator, v.vin, v.vehicle_name, v.fuel_type
                    ),
                ]
            )
    async_add_entities(entities)


class HondaClimateTempSelect(MyHondaPlusEntity, SelectEntity):
    """Select entity for climate temperature setting."""

    _attr_icon = "mdi:thermometer"
    _attr_translation_key = "climate_temp_setting"
    _attr_options = CLIMATE_TEMP_OPTIONS
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator, vin: str, vehicle_name: str, fuel_type: str = ""
    ) -> None:
        description = SelectEntityDescription(
            key="climate_temp_setting",
            translation_key="climate_temp_setting",
        )
        super().__init__(coordinator, description, vin, vehicle_name, fuel_type)

    @property
    def current_option(self) -> str | None:
        value = self.coordinator.data.climate_temp
        if value in CLIMATE_TEMP_OPTIONS:
            return value
        return "normal"

    async def async_select_option(self, option: str) -> None:
        """Update climate temperature setting on the vehicle."""
        data = self.coordinator.data
        duration = data.climate_duration
        if duration not in (10, 20, 30):
            duration = 30
        defrost = data.climate_defrost
        confirmed = await self.coordinator.async_send_command_and_wait(
            self.coordinator.api.set_climate_settings,
            self._vin,
            option,
            duration,
            defrost,
        )
        if confirmed:
            self.coordinator.async_set_updated_data(
                replace(self.coordinator.data, climate_temp=option)
            )


class HondaClimateDurationSelect(MyHondaPlusEntity, SelectEntity):
    """Select entity for climate duration setting."""

    _attr_icon = "mdi:timer-outline"
    _attr_translation_key = "climate_duration_setting"
    _attr_options = CLIMATE_DURATION_OPTIONS
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator, vin: str, vehicle_name: str, fuel_type: str = ""
    ) -> None:
        description = SelectEntityDescription(
            key="climate_duration_setting",
            translation_key="climate_duration_setting",
        )
        super().__init__(coordinator, description, vin, vehicle_name, fuel_type)

    @property
    def current_option(self) -> str | None:
        value = self.coordinator.data.climate_duration
        if value in (10, 20, 30):
            return str(value)
        return "30"

    async def async_select_option(self, option: str) -> None:
        """Update climate duration setting on the vehicle."""
        data = self.coordinator.data
        temp = data.climate_temp
        if temp not in CLIMATE_TEMP_OPTIONS:
            temp = "normal"
        defrost = data.climate_defrost
        duration = int(option)
        confirmed = await self.coordinator.async_send_command_and_wait(
            self.coordinator.api.set_climate_settings,
            self._vin,
            temp,
            duration,
            defrost,
        )
        if confirmed:
            self.coordinator.async_set_updated_data(
                replace(self.coordinator.data, climate_duration=duration)
            )
