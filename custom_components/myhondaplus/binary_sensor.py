"""Binary sensor platform for My Honda+."""

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_VEHICLE_NAME, CONF_VIN
from .data import MyHondaPlusConfigEntry
from .entity import MyHondaPlusEntity


@dataclass(frozen=True, kw_only=True)
class HondaBinarySensorDescription(BinarySensorEntityDescription):
    data_key: str = ""
    invert: bool = False


BINARY_SENSOR_DESCRIPTIONS: list[HondaBinarySensorDescription] = [
    HondaBinarySensorDescription(
        key="doors_open",
        translation_key="doors_open",
        device_class=BinarySensorDeviceClass.DOOR,
        icon="mdi:car-door",
        data_key="all_doors_closed",
        invert=True,
    ),
    HondaBinarySensorDescription(
        key="windows_open",
        translation_key="windows_open",
        device_class=BinarySensorDeviceClass.WINDOW,
        icon="mdi:car-door",
        data_key="all_windows_closed",
        invert=True,
    ),
    HondaBinarySensorDescription(
        key="hood",
        translation_key="hood",
        device_class=BinarySensorDeviceClass.OPENING,
        icon="mdi:car",
        data_key="hood_open",
    ),
    HondaBinarySensorDescription(
        key="trunk",
        translation_key="trunk",
        device_class=BinarySensorDeviceClass.OPENING,
        icon="mdi:car-back",
        data_key="trunk_open",
    ),
    HondaBinarySensorDescription(
        key="lights",
        translation_key="lights",
        device_class=BinarySensorDeviceClass.LIGHT,
        icon="mdi:car-light-high",
        data_key="lights_on",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyHondaPlusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up My Honda+ binary sensors."""
    coordinator = entry.runtime_data.coordinator
    vin = entry.data[CONF_VIN]
    vehicle_name = entry.data.get(CONF_VEHICLE_NAME, "")
    async_add_entities(
        HondaBinarySensor(coordinator, description, vin, vehicle_name)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


def _to_bool(value) -> bool | None:
    """Convert a value to bool, handling strings from the API."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "on", "yes", "1")
    return bool(value)


class HondaBinarySensor(MyHondaPlusEntity, BinarySensorEntity):
    """My Honda+ binary sensor entity."""

    entity_description: HondaBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.data.get(self.entity_description.data_key)
        result = _to_bool(value)
        if result is None:
            return None
        if self.entity_description.invert:
            return not result
        return result
