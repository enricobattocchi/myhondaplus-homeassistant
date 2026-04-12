"""Number platform for My Honda+ (charge limits)."""

from dataclasses import dataclass, replace

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
        if v.capabilities.remote_charge and v.capabilities.max_charge:
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
        val = getattr(self.coordinator.data, self.entity_description.key, None)
        return float(val) if val is not None else None

    @property
    def assumed_state(self) -> bool:
        return False

    async def async_set_native_value(self, value: float) -> None:
        data = self.coordinator.data
        home = data.charge_limit_home
        away = data.charge_limit_away

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
            self.coordinator.async_set_updated_data(
                replace(data, **{self.entity_description.key: int(value)})
            )
