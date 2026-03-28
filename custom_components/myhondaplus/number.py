"""Number platform for My Honda+ (charge limits)."""

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_VEHICLE_NAME, CONF_VIN
from .data import MyHondaPlusConfigEntry
from .entity import MyHondaPlusEntity


@dataclass(frozen=True, kw_only=True)
class HondaNumberDescription(NumberEntityDescription):
    limit_key: str = ""


NUMBER_DESCRIPTIONS: list[HondaNumberDescription] = [
    HondaNumberDescription(
        key="charge_limit_home",
        translation_key="charge_limit_home",
        icon="mdi:battery-charging-80",
        native_min_value=80,
        native_max_value=100,
        native_step=5,
        native_unit_of_measurement=PERCENTAGE,
        limit_key="home",
    ),
    HondaNumberDescription(
        key="charge_limit_away",
        translation_key="charge_limit_away",
        icon="mdi:battery-charging-90",
        native_min_value=80,
        native_max_value=100,
        native_step=5,
        native_unit_of_measurement=PERCENTAGE,
        limit_key="away",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyHondaPlusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up My Honda+ charge limit numbers."""
    coordinator = entry.runtime_data.coordinator
    vin = entry.data[CONF_VIN]
    vehicle_name = entry.data.get(CONF_VEHICLE_NAME, "")
    async_add_entities(
        HondaChargeLimitNumber(coordinator, description, vin, vehicle_name)
        for description in NUMBER_DESCRIPTIONS
    )


class HondaChargeLimitNumber(MyHondaPlusEntity, NumberEntity):
    """My Honda+ charge limit number entity."""

    @property
    def native_value(self) -> float | None:
        val = self.coordinator.data.get(self.entity_description.key)
        return float(val) if val is not None else None

    @property
    def assumed_state(self) -> bool:
        return False

    async def async_set_native_value(self, value: float) -> None:
        data = self.coordinator.data or {}
        home = data.get("charge_limit_home", 80)
        away = data.get("charge_limit_away", 90)

        if self.entity_description.limit_key == "home":
            home = int(value)
        else:
            away = int(value)

        confirmed = await self.coordinator.async_send_command_and_wait(
            self.coordinator.api.set_charge_limit, self._vin, home, away,
        )
        if confirmed and self.coordinator.data is not None:
            data = dict(self.coordinator.data)
            data[self.entity_description.key] = int(value)
            self.coordinator.async_set_updated_data(data)
