"""Button platform for My Honda+."""

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .data import MyHondaPlusConfigEntry
from .entity import MyHondaPlusEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class HondaButtonDescription(ButtonEntityDescription):
    action: str = ""
    capability: str = ""


BUTTON_DESCRIPTIONS: list[HondaButtonDescription] = [
    HondaButtonDescription(
        key="horn_lights",
        translation_key="horn_lights",
        icon="mdi:bullhorn",
        action="horn_lights",
        capability="remote_horn",
    ),
    HondaButtonDescription(
        key="refresh_cached",
        translation_key="refresh_cached",
        icon="mdi:refresh",
        action="refresh_cached",
    ),
    HondaButtonDescription(
        key="refresh_data",
        translation_key="refresh_data",
        icon="mdi:refresh-circle",
        action="refresh",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyHondaPlusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up My Honda+ buttons."""
    entities = []
    for v in entry.runtime_data.vehicles.values():
        entities.extend(
            HondaButton(v.coordinator, desc, v.vin, v.vehicle_name, v.fuel_type)
            for desc in BUTTON_DESCRIPTIONS
            if not desc.capability
            or getattr(v.capabilities, desc.capability, True)
        )
    async_add_entities(entities)


class HondaButton(MyHondaPlusEntity, ButtonEntity):
    """My Honda+ button entity."""

    async def async_press(self) -> None:
        action = self.entity_description.action
        api = self.coordinator.api
        vin = self._vin

        if action == "horn_lights":
            await self.coordinator.async_send_command_and_wait(
                api.remote_horn_lights, vin
            )
        elif action == "refresh_cached":
            await self.coordinator.async_request_refresh()
        elif action == "refresh":
            await self.coordinator.async_refresh_from_car()
