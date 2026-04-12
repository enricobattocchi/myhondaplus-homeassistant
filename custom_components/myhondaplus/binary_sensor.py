"""Binary sensor platform for My Honda+."""

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .data import MyHondaPlusConfigEntry
from .entity import MyHondaPlusEntity, to_bool

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class HondaBinarySensorDescription(BinarySensorEntityDescription):
    data_key: str = ""
    invert: bool = False
    ui_hide: str = ""


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
        ui_hide="hide_window_status",
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
    entities = []
    for vehicle in entry.runtime_data.vehicles.values():
        entities.extend(
            HondaBinarySensor(
                vehicle.coordinator,
                desc,
                vehicle.vin,
                vehicle.vehicle_name,
                vehicle.fuel_type,
            )
            for desc in BINARY_SENSOR_DESCRIPTIONS
            if not desc.ui_hide
            or not getattr(vehicle.ui_config, desc.ui_hide, False)
        )
    async_add_entities(entities)


class HondaBinarySensor(MyHondaPlusEntity, BinarySensorEntity):
    """My Honda+ binary sensor entity."""

    entity_description: HondaBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        value = getattr(self.coordinator.data, self.entity_description.data_key, None)
        result = to_bool(value)
        if result is None:
            return None
        if self.entity_description.invert:
            return not result
        return result
