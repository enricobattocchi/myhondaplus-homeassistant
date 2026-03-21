"""Sensor platform for My Honda+."""

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfLength,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_VEHICLE_NAME, CONF_VIN
from .data import MyHondaPlusConfigEntry
from .entity import MyHondaPlusEntity


@dataclass(frozen=True, kw_only=True)
class HondaSensorDescription(SensorEntityDescription):
    pass


SENSOR_DESCRIPTIONS: list[HondaSensorDescription] = [
    HondaSensorDescription(
        key="battery_level",
        translation_key="battery_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HondaSensorDescription(
        key="range_km",
        translation_key="range",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:map-marker-distance",
    ),
    HondaSensorDescription(
        key="total_range_km",
        translation_key="total_range",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:map-marker-distance",
    ),
    HondaSensorDescription(
        key="charge_status",
        translation_key="charge_status",
        icon="mdi:ev-station",
    ),
    HondaSensorDescription(
        key="plug_status",
        translation_key="plug_status",
        icon="mdi:power-plug",
    ),
    HondaSensorDescription(
        key="home_away",
        translation_key="home_away",
        icon="mdi:home-map-marker",
    ),
    HondaSensorDescription(
        key="climate_active",
        translation_key="climate_active",
        icon="mdi:air-conditioner",
    ),
    HondaSensorDescription(
        key="cabin_temp_c",
        translation_key="cabin_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HondaSensorDescription(
        key="odometer_km",
        translation_key="odometer",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:counter",
    ),
    HondaSensorDescription(
        key="doors_locked",
        translation_key="doors_locked",
        icon="mdi:car-door-lock",
    ),
    HondaSensorDescription(
        key="all_doors_closed",
        translation_key="doors_closed",
        icon="mdi:car-door",
    ),
    HondaSensorDescription(
        key="all_windows_closed",
        translation_key="windows_closed",
        icon="mdi:car-door",
    ),
    HondaSensorDescription(
        key="ignition",
        translation_key="ignition",
        icon="mdi:car-key",
    ),
    HondaSensorDescription(
        key="speed_kmh",
        translation_key="speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:speedometer",
    ),
    HondaSensorDescription(
        key="charge_mode",
        translation_key="charge_mode",
        icon="mdi:ev-station",
    ),
    HondaSensorDescription(
        key="time_to_charge",
        translation_key="time_to_charge",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery-clock",
    ),
    HondaSensorDescription(
        key="interior_temp_c",
        translation_key="interior_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HondaSensorDescription(
        key="hood_open",
        translation_key="hood",
        icon="mdi:car",
    ),
    HondaSensorDescription(
        key="trunk_open",
        translation_key="trunk",
        icon="mdi:car-back",
    ),
    HondaSensorDescription(
        key="lights_on",
        translation_key="lights",
        icon="mdi:car-light-high",
    ),
    HondaSensorDescription(
        key="headlights",
        translation_key="headlights",
        icon="mdi:car-light-high",
    ),
    HondaSensorDescription(
        key="parking_lights",
        translation_key="parking_lights",
        icon="mdi:car-parking-lights",
    ),
    HondaSensorDescription(
        key="warning_lamps",
        translation_key="warnings",
        icon="mdi:alert",
    ),
    HondaSensorDescription(
        key="latitude",
        translation_key="latitude",
        icon="mdi:crosshairs-gps",
    ),
    HondaSensorDescription(
        key="longitude",
        translation_key="longitude",
        icon="mdi:crosshairs-gps",
    ),
    HondaSensorDescription(
        key="timestamp",
        translation_key="last_updated",
        icon="mdi:clock-outline",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyHondaPlusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up My Honda+ sensors."""
    coordinator = entry.runtime_data.coordinator
    vin = entry.data[CONF_VIN]
    vehicle_name = entry.data.get(CONF_VEHICLE_NAME, "")
    async_add_entities(
        HondaSensor(coordinator, description, vin, vehicle_name)
        for description in SENSOR_DESCRIPTIONS
    )


class HondaSensor(MyHondaPlusEntity, SensorEntity):
    """My Honda+ sensor entity."""

    @property
    def native_value(self):
        value = self.coordinator.data.get(self.entity_description.key)
        if isinstance(value, list):
            return ", ".join(str(v) for v in value) if value else "none"
        return value
