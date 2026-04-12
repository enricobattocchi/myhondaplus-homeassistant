"""Sensor platform for My Honda+."""

from dataclasses import dataclass
from datetime import datetime

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
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .data import MyHondaPlusConfigEntry
from .entity import MyHondaPlusEntity

PARALLEL_UPDATES = 0

UNIT_MAP = {
    "km": {"distance": "km", "speed": "km/h", "temp": "°C"},
    "miles": {"distance": "mi", "speed": "mph", "temp": "°F"},
}


@dataclass(frozen=True, kw_only=True)
class HondaSensorDescription(SensorEntityDescription):
    dynamic_unit: str = ""
    capability: str = ""
    ui_hide: str = ""


SENSOR_DESCRIPTIONS: list[HondaSensorDescription] = [
    HondaSensorDescription(
        key="battery_level",
        translation_key="battery_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        capability="remote_charge",
    ),
    HondaSensorDescription(
        key="range_climate_on",
        translation_key="range_climate_on",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:map-marker-distance",
        dynamic_unit="distance",
        capability="remote_charge",
    ),
    HondaSensorDescription(
        key="range_climate_off",
        translation_key="range_climate_off",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:map-marker-distance",
        dynamic_unit="distance",
        capability="remote_charge",
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
        device_class=SensorDeviceClass.ENUM,
        options=["stopped", "charging", "complete", "notcharging", "unknown"],
        icon="mdi:ev-station",
        capability="remote_charge",
    ),
    HondaSensorDescription(
        key="plug_status",
        translation_key="plug_status",
        device_class=SensorDeviceClass.ENUM,
        options=["plugged_in", "connected", "unplugged", "disconnected", "unknown"],
        icon="mdi:power-plug",
        capability="remote_charge",
    ),
    HondaSensorDescription(
        key="home_away",
        translation_key="home_away",
        device_class=SensorDeviceClass.ENUM,
        options=["home", "away", "unknown"],
        icon="mdi:home-map-marker",
    ),
    HondaSensorDescription(
        key="climate_active",
        translation_key="climate_active",
        icon="mdi:air-conditioner",
        capability="remote_climate",
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
        device_class=SensorDeviceClass.ENUM,
        options=[
            "unconfirmed",
            "100v_charging",
            "200v_charging",
            "fast_charging",
            "unknown",
        ],
        icon="mdi:ev-station",
        capability="remote_charge",
    ),
    HondaSensorDescription(
        key="time_to_charge",
        translation_key="time_to_charge",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery-clock",
        capability="remote_charge",
    ),
    HondaSensorDescription(
        key="interior_temp",
        translation_key="interior_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        dynamic_unit="temp",
        ui_hide="hide_internal_temperature",
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
        key="timestamp",
        translation_key="last_updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    HondaSensorDescription(
        key="climate_temp",
        translation_key="climate_temp",
        device_class=SensorDeviceClass.ENUM,
        options=["cooler", "normal", "hotter", "unknown"],
        icon="mdi:thermometer",
        capability="remote_climate",
    ),
    HondaSensorDescription(
        key="climate_duration",
        translation_key="climate_duration",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:timer-outline",
        capability="remote_climate",
    ),
    HondaSensorDescription(
        key="climate_defrost",
        translation_key="climate_defrost",
        icon="mdi:car-defrost-rear",
        capability="remote_climate",
    ),
    HondaSensorDescription(
        key="charge_schedule",
        translation_key="charge_schedule",
        icon="mdi:calendar-clock",
        entity_category=EntityCategory.DIAGNOSTIC,
        capability="charge_schedule",
    ),
    HondaSensorDescription(
        key="climate_schedule",
        translation_key="climate_schedule",
        icon="mdi:calendar-clock",
        entity_category=EntityCategory.DIAGNOSTIC,
        capability="climate_schedule",
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


def _sensor_enabled(
    desc: HondaSensorDescription, vehicle,
) -> bool:
    """Check if a sensor should be created based on capabilities and UI config."""
    if desc.capability and not getattr(vehicle.capabilities, desc.capability, True):
        return False
    if desc.ui_hide and getattr(vehicle.ui_config, desc.ui_hide, False):
        return False
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyHondaPlusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up My Honda+ sensors."""
    entities: list[SensorEntity] = []
    for vehicle in entry.runtime_data.vehicles.values():
        vin = vehicle.vin
        name = vehicle.vehicle_name
        fuel_type = vehicle.fuel_type
        entities.extend(
            HondaSensor(vehicle.coordinator, desc, vin, name, fuel_type)
            for desc in SENSOR_DESCRIPTIONS
            if _sensor_enabled(desc, vehicle)
        )
        if vehicle.capabilities.journey_history:
            entities.extend(
                HondaTripSensor(vehicle.trip_coordinator, desc, vin, name, fuel_type)
                for desc in TRIP_SENSOR_DESCRIPTIONS
            )
    async_add_entities(entities)


def _resolve_unit(data, description: HondaSensorDescription) -> str | None:
    """Resolve the unit of measurement from coordinator data."""
    if not description.dynamic_unit or not data:
        return description.native_unit_of_measurement
    distance_unit = data.distance_unit if hasattr(data, "distance_unit") else "km"
    units = UNIT_MAP.get(distance_unit, UNIT_MAP["km"])
    return units.get(description.dynamic_unit)


SCHEDULE_KEYS = {"charge_schedule", "climate_schedule"}


class HondaSensor(MyHondaPlusEntity, SensorEntity):
    """My Honda+ sensor entity."""

    @property
    def native_value(self):
        value = getattr(self.coordinator.data, self.entity_description.key, None)
        if self.entity_description.key in SCHEDULE_KEYS:
            if not isinstance(value, list):
                return 0
            return sum(1 for r in value if r.get("enabled"))
        if isinstance(value, list):
            return ", ".join(str(v) for v in value) if value else "none"
        if (
            self.entity_description.device_class == SensorDeviceClass.TIMESTAMP
            and isinstance(value, str)
        ):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        if (
            self.entity_description.device_class == SensorDeviceClass.ENUM
            and isinstance(value, str)
        ):
            return value.replace(" ", "_")
        return value

    @property
    def native_unit_of_measurement(self) -> str | None:
        return _resolve_unit(self.coordinator.data, self.entity_description)

    @property
    def extra_state_attributes(self) -> dict | None:
        if self.entity_description.key not in SCHEDULE_KEYS:
            return None
        value = getattr(self.coordinator.data, self.entity_description.key, None)
        if not isinstance(value, list):
            return None
        return {"rules": value}


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
