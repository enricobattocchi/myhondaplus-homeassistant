"""Button platform for My Honda+."""

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_VEHICLE_NAME, CONF_VIN
from .data import MyHondaPlusConfigEntry
from .entity import MyHondaPlusEntity


@dataclass(frozen=True, kw_only=True)
class HondaButtonDescription(ButtonEntityDescription):
    action: str = ""


BUTTON_DESCRIPTIONS: list[HondaButtonDescription] = [
    HondaButtonDescription(
        key="horn_lights",
        translation_key="horn_lights",
        icon="mdi:bullhorn",
        action="horn_lights",
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
    entry: MyHondaPlusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up My Honda+ buttons."""
    coordinator = entry.runtime_data.coordinator
    vin = entry.data[CONF_VIN]
    vehicle_name = entry.data.get(CONF_VEHICLE_NAME, "")
    async_add_entities(
        HondaButton(coordinator, description, vin, vehicle_name)
        for description in BUTTON_DESCRIPTIONS
    )


class HondaButton(MyHondaPlusEntity, ButtonEntity):
    """My Honda+ button entity."""

    async def async_press(self) -> None:
        action = self.entity_description.action
        api = self.coordinator.api
        vin = self._vin

        if action == "horn_lights":
            await self.coordinator.async_send_command_and_wait(api.remote_horn_lights, vin)
        elif action == "refresh":
            await self.coordinator.async_refresh_from_car()
