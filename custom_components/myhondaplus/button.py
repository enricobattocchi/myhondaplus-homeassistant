"""Button platform for My Honda+."""

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_VIN, DOMAIN
from .coordinator import HondaDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class HondaButtonDescription(ButtonEntityDescription):
    action: str = ""


BUTTON_DESCRIPTIONS: list[HondaButtonDescription] = [
    HondaButtonDescription(
        key="lock",
        translation_key="lock",
        icon="mdi:car-door-lock",
        action="lock",
    ),
    HondaButtonDescription(
        key="unlock",
        translation_key="unlock",
        icon="mdi:car-door",
        action="unlock",
    ),
    HondaButtonDescription(
        key="horn_lights",
        translation_key="horn_lights",
        icon="mdi:bullhorn",
        action="horn_lights",
    ),
    HondaButtonDescription(
        key="climate_start",
        translation_key="climate_start",
        icon="mdi:air-conditioner",
        action="climate_start",
    ),
    HondaButtonDescription(
        key="climate_stop",
        translation_key="climate_stop",
        icon="mdi:fan-off",
        action="climate_stop",
    ),
    HondaButtonDescription(
        key="refresh_data",
        translation_key="refresh_data",
        icon="mdi:refresh",
        action="refresh",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: HondaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    vin = entry.data[CONF_VIN]
    async_add_entities(
        HondaButton(coordinator, description, vin)
        for description in BUTTON_DESCRIPTIONS
    )


class HondaButton(CoordinatorEntity[HondaDataUpdateCoordinator], ButtonEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HondaDataUpdateCoordinator,
        description: HondaButtonDescription,
        vin: str,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{vin}_{description.key}"
        self._vin = vin

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._vin)},
            name=f"Honda {self._vin[-6:]}",
            manufacturer="Honda",
        )

    async def async_press(self) -> None:
        action = self.entity_description.action
        api = self.coordinator.api
        vin = self._vin

        if action == "lock":
            await self.coordinator.async_send_command(api.remote_lock, vin)
        elif action == "unlock":
            await self.coordinator.async_send_command(api.remote_unlock, vin)
        elif action == "horn_lights":
            await self.coordinator.async_send_command(api.remote_horn_lights, vin)
        elif action == "climate_start":
            await self.coordinator.async_send_command(api.remote_climate_start, vin)
        elif action == "climate_stop":
            await self.coordinator.async_send_command(api.remote_climate_stop, vin)
        elif action == "refresh":
            await self.coordinator.async_refresh_from_car()
            self.hass.async_create_task(
                self._delayed_refresh()
            )

    async def _delayed_refresh(self) -> None:
        import asyncio
        await asyncio.sleep(30)
        await self.coordinator.async_request_refresh()
