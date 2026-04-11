"""Number platform for My Honda+ (charge limits)."""

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .data import MyHondaPlusConfigEntry
from .entity import MyHondaPlusEntity

PARALLEL_UPDATES = 1


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
    entities = []
    for v in entry.runtime_data.vehicles.values():
        entities.extend(
            HondaChargeLimitNumber(
                v.coordinator, desc, v.vin, v.vehicle_name, v.fuel_type
            )
            for desc in NUMBER_DESCRIPTIONS
        )
    async_add_entities(entities)


class HondaChargeLimitNumber(MyHondaPlusEntity, NumberEntity):
    """My Honda+ charge limit number entity."""

    _attr_entity_category = EntityCategory.CONFIG

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
            self.coordinator.api.set_charge_limit,
            self._vin,
            home,
            away,
        )
        if confirmed:
            new_data = dict(self.coordinator.data)
            new_data[self.entity_description.key] = int(value)
            self.coordinator.async_set_updated_data(new_data)
