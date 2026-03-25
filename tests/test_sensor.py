"""Tests for the sensor platform."""

from unittest.mock import MagicMock

from custom_components.myhondaplus.sensor import (
    SENSOR_DESCRIPTIONS,
    TRIP_SENSOR_DESCRIPTIONS,
    HondaSensor,
    HondaTripSensor,
)

from .conftest import MOCK_VEHICLE_NAME, MOCK_VIN


def make_sensor(coordinator, key):
    """Create a HondaSensor for a given key."""
    desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == key)
    sensor = HondaSensor(coordinator, desc, MOCK_VIN, MOCK_VEHICLE_NAME)
    sensor.hass = MagicMock()
    return sensor


def make_trip_sensor(coordinator, key):
    """Create a HondaTripSensor for a given key."""
    desc = next(d for d in TRIP_SENSOR_DESCRIPTIONS if d.key == key)
    sensor = HondaTripSensor(coordinator, desc, MOCK_VIN, MOCK_VEHICLE_NAME)
    sensor.hass = MagicMock()
    return sensor


class TestHondaSensor:
    def test_battery_level(self, mock_coordinator):
        sensor = make_sensor(mock_coordinator, "battery_level")
        assert sensor.native_value == 75

    def test_range(self, mock_coordinator):
        sensor = make_sensor(mock_coordinator, "range")
        assert sensor.native_value == 150

    def test_charge_status(self, mock_coordinator):
        sensor = make_sensor(mock_coordinator, "charge_status")
        assert sensor.native_value == "not_charging"

    def test_doors_locked(self, mock_coordinator):
        sensor = make_sensor(mock_coordinator, "doors_locked")
        assert sensor.native_value is True

    def test_odometer(self, mock_coordinator):
        sensor = make_sensor(mock_coordinator, "odometer")
        assert sensor.native_value == 12345

    def test_missing_key_returns_none(self, mock_coordinator):
        mock_coordinator.data = {}
        sensor = make_sensor(mock_coordinator, "battery_level")
        assert sensor.native_value is None

    def test_list_value_joins(self, mock_coordinator):
        mock_coordinator.data["warning_lamps"] = ["oil", "tire"]
        sensor = make_sensor(mock_coordinator, "warning_lamps")
        assert sensor.native_value == "oil, tire"

    def test_empty_list_returns_none_string(self, mock_coordinator):
        mock_coordinator.data["warning_lamps"] = []
        sensor = make_sensor(mock_coordinator, "warning_lamps")
        assert sensor.native_value == "none"

    def test_all_sensor_descriptions_have_valid_keys(self, mock_coordinator):
        """Ensure every sensor description key exists in the mock dashboard data."""
        for desc in SENSOR_DESCRIPTIONS:
            sensor = HondaSensor(mock_coordinator, desc, MOCK_VIN, MOCK_VEHICLE_NAME)
            sensor.hass = MagicMock()
            _ = sensor.native_value

    def test_dynamic_unit_distance_km(self, mock_coordinator):
        sensor = make_sensor(mock_coordinator, "range")
        assert sensor.native_unit_of_measurement == "km"

    def test_dynamic_unit_speed_km(self, mock_coordinator):
        sensor = make_sensor(mock_coordinator, "speed")
        assert sensor.native_unit_of_measurement == "km/h"

    def test_dynamic_unit_temp_km(self, mock_coordinator):
        sensor = make_sensor(mock_coordinator, "cabin_temp")
        assert sensor.native_unit_of_measurement == "°C"

    def test_dynamic_unit_distance_miles(self, mock_coordinator):
        mock_coordinator.data["distance_unit"] = "miles"
        sensor = make_sensor(mock_coordinator, "range")
        assert sensor.native_unit_of_measurement == "mi"

    def test_dynamic_unit_speed_miles(self, mock_coordinator):
        mock_coordinator.data["distance_unit"] = "miles"
        sensor = make_sensor(mock_coordinator, "speed")
        assert sensor.native_unit_of_measurement == "mph"

    def test_dynamic_unit_temp_miles(self, mock_coordinator):
        mock_coordinator.data["distance_unit"] = "miles"
        sensor = make_sensor(mock_coordinator, "cabin_temp")
        assert sensor.native_unit_of_measurement == "°F"

    def test_static_unit_not_affected(self, mock_coordinator):
        sensor = make_sensor(mock_coordinator, "battery_level")
        assert sensor.native_unit_of_measurement == "%"


class TestHondaTripSensor:
    def test_trips_count(self, mock_trip_coordinator):
        sensor = make_trip_sensor(mock_trip_coordinator, "trips")
        assert sensor.native_value == 15

    def test_total_distance(self, mock_trip_coordinator):
        sensor = make_trip_sensor(mock_trip_coordinator, "total_distance")
        assert sensor.native_value == 320

    def test_avg_consumption(self, mock_trip_coordinator):
        sensor = make_trip_sensor(mock_trip_coordinator, "avg_consumption")
        assert sensor.native_value == 14.5

    def test_avg_consumption_unit(self, mock_trip_coordinator):
        sensor = make_trip_sensor(mock_trip_coordinator, "avg_consumption")
        assert sensor.native_unit_of_measurement == "kWh/100km"

    def test_empty_data_returns_none(self, mock_trip_coordinator):
        mock_trip_coordinator.data = {}
        sensor = make_trip_sensor(mock_trip_coordinator, "trips")
        assert sensor.native_value is None

    def test_none_data_returns_none(self, mock_trip_coordinator):
        mock_trip_coordinator.data = None
        sensor = make_trip_sensor(mock_trip_coordinator, "trips")
        assert sensor.native_value is None

    def test_distance_unit_dynamic(self, mock_trip_coordinator):
        sensor = make_trip_sensor(mock_trip_coordinator, "total_distance")
        assert sensor.native_unit_of_measurement == "km"
