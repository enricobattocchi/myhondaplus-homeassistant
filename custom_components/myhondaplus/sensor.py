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
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_VEHICLE_NAME, CONF_VIN
from .data import MyHondaPlusConfigEntry
from .entity import MyHondaPlusEntity

UNIT_MAP = {
    "km": {"distance": "km", "speed": "km/h", "temp": "°C"},
    "miles": {"distance": "mi", "speed": "mph", "temp": "°F"},
}


@dataclass(frozen=True, kw_only=True)
class HondaSensorDescription(SensorEntityDescription):
    dynamic_unit: str = ""


SENSOR_DESCRIPTIONS: list[HondaSensorDescription] = [
    HondaSensorDescription(
        key="battery_level",
        translation_key="battery_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HondaSensorDescription(
        key="range",
        translation_key="range",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:map-marker-distance",
        dynamic_unit="distance",
    ),
    HondaSensorDescription(
        key="total_range",
        translation_key="total_range",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:map-marker-distance",
        dynamic_unit="distance",
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
        key="cabin_temp",
        translation_key="cabin_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        dynamic_unit="temp",
    ),
    HondaSensorDescription(
        key="odometer",
        translation_key="odometer",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:counter",
        dynamic_unit="distance",
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
        key="speed",
        translation_key="speed",
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:speedometer",
        dynamic_unit="speed",
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
        key="interior_temp",
        translation_key="interior_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        dynamic_unit="temp",
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


TRIP_SENSOR_DESCRIPTIONS: list[HondaSensorDescription] = [
    HondaSensorDescription(
        key="trips",
        translation_key="trips_this_month",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:car-multiple",
    ),
    HondaSensorDescription(
        key="total_distance",
        translation_key="distance_this_month",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:map-marker-distance",
        dynamic_unit="distance",
    ),
    HondaSensorDescription(
        key="total_minutes",
        translation_key="driving_time_this_month",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:clock-outline",
    ),
    HondaSensorDescription(
        key="avg_consumption",
        translation_key="avg_consumption_this_month",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gas-station",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyHondaPlusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up My Honda+ sensors."""
    coordinator = entry.runtime_data.coordinator
    trip_coordinator = entry.runtime_data.trip_coordinator
    vin = entry.data[CONF_VIN]
    vehicle_name = entry.data.get(CONF_VEHICLE_NAME, "")
    entities: list[SensorEntity] = [
        HondaSensor(coordinator, description, vin, vehicle_name)
        for description in SENSOR_DESCRIPTIONS
    ]
    entities.extend(
        HondaTripSensor(trip_coordinator, description, vin, vehicle_name)
        for description in TRIP_SENSOR_DESCRIPTIONS
    )
    async_add_entities(entities)


def _resolve_unit(data: dict, description: HondaSensorDescription) -> str | None:
    """Resolve the unit of measurement from coordinator data."""
    if not description.dynamic_unit or not data:
        return description.native_unit_of_measurement
    distance_unit = data.get("distance_unit", "km")
    units = UNIT_MAP.get(distance_unit, UNIT_MAP["km"])
    return units.get(description.dynamic_unit)


class HondaSensor(MyHondaPlusEntity, SensorEntity):
    """My Honda+ sensor entity."""

    @property
    def native_value(self):
        value = self.coordinator.data.get(self.entity_description.key)
        if isinstance(value, list):
            return ", ".join(str(v) for v in value) if value else "none"
        return value

    @property
    def native_unit_of_measurement(self) -> str | None:
        return _resolve_unit(self.coordinator.data, self.entity_description)


class HondaTripSensor(MyHondaPlusEntity, SensorEntity):
    """My Honda+ trip statistics sensor."""

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.key == "avg_consumption" and self.coordinator.data:
            return self.coordinator.data.get("consumption_unit")
        return _resolve_unit(self.coordinator.data, self.entity_description)
