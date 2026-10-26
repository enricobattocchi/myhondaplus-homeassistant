"""Tests for the sensor platform."""

from unittest.mock import MagicMock

import pytest

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

    def test_range_climate_on(self, mock_coordinator):
        sensor = make_sensor(mock_coordinator, "range_climate_on")
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

    def test_fuel_level(self, mock_coordinator):
        mock_coordinator.data.has_fuel = True
        mock_coordinator.data.fuel_level = 24
        sensor = make_sensor(mock_coordinator, "fuel_level")
        assert sensor.native_value == 24

    def test_fuel_level_empty_tank(self, mock_coordinator):
        mock_coordinator.data.has_fuel = True
        mock_coordinator.data.fuel_level = 0
        sensor = make_sensor(mock_coordinator, "fuel_level")
        assert sensor.native_value == 0

    def test_fuel_sensors_unknown_without_fuel_gauge(self, mock_coordinator):
        mock_coordinator.data.has_fuel = False
        for key in ("fuel_level", "fuel_range"):
            assert make_sensor(mock_coordinator, key).native_value is None

    def test_fuel_range(self, mock_coordinator):
        mock_coordinator.data.has_fuel = True
        mock_coordinator.data.fuel_range = 153
        sensor = make_sensor(mock_coordinator, "fuel_range")
        assert sensor.native_value == 153
        assert sensor.native_unit_of_measurement == "km"

    def test_fuel_range_unit_follows_distance_unit(self, mock_coordinator):
        mock_coordinator.data.has_fuel = True
        mock_coordinator.data.distance_unit = "miles"
        sensor = make_sensor(mock_coordinator, "fuel_range")
        assert sensor.native_unit_of_measurement == "mi"

    def test_missing_key_returns_none(self, mock_coordinator):
        mock_coordinator.data = {}
        sensor = make_sensor(mock_coordinator, "battery_level")
        assert sensor.native_value is None

    def test_list_value_joins(self, mock_coordinator):
        mock_coordinator.data.warning_lamps = ["oil", "tire"]
        sensor = make_sensor(mock_coordinator, "warning_lamps")
        assert sensor.native_value == "oil, tire"

    def test_empty_list_returns_none_string(self, mock_coordinator):
        mock_coordinator.data.warning_lamps = []
        sensor = make_sensor(mock_coordinator, "warning_lamps")
        assert sensor.native_value == "none"

    @pytest.mark.parametrize("length", [255, 256])
    def test_warning_state_length_boundary(self, mock_coordinator, length):
        indicators = ["x" * length]
        mock_coordinator.data.warning_lamps = indicators
        sensor = make_sensor(mock_coordinator, "warning_lamps")
        assert sensor.native_value == (indicators[0] if length == 255 else "1")
        assert sensor.extra_state_attributes == {"indicators": indicators}

    def test_many_warning_indicators_are_preserved(self, mock_coordinator):
        indicators = [
            f"MeterIndicator_{name}"
            for name in (
                "TPMS_DWS", "Engine_Failure", "LKAS_Amber", "CMBS", "RDM", "EPS",
                "BATT", "ACC_Amber", "Seatbelt", "Brake_Amber", "VSA_Off", "VSA_Act",
                "Brake_Red", "ABS", "SRS", "Safety_Failure", "PowerSystem_Failure",
            )
        ]
        mock_coordinator.data.warning_lamps = indicators
        sensor = make_sensor(mock_coordinator, "warning_lamps")
        assert len(", ".join(indicators)) > 255
        assert sensor.native_value == "17"
        assert sensor.extra_state_attributes == {"indicators": indicators}

        mock_coordinator.data.warning_lamps = ["MeterIndicator_Seatbelt"]
        assert sensor.native_value == "MeterIndicator_Seatbelt"
        assert sensor.extra_state_attributes == {"indicators": ["MeterIndicator_Seatbelt"]}

        mock_coordinator.data.warning_lamps = []
        assert sensor.native_value == "none"
        assert sensor.extra_state_attributes == {"indicators": []}

    def test_short_warning_list_has_indicators_attribute(self, mock_coordinator):
        mock_coordinator.data.warning_lamps = ["oil", "tire"]
        sensor = make_sensor(mock_coordinator, "warning_lamps")
        assert sensor.native_value == "oil, tire"
        assert sensor.extra_state_attributes == {"indicators": ["oil", "tire"]}

    def test_missing_warning_list_has_no_attributes(self, mock_coordinator):
        mock_coordinator.data.warning_lamps = None
        sensor = make_sensor(mock_coordinator, "warning_lamps")
        assert sensor.native_value is None
        assert sensor.extra_state_attributes is None

    def test_all_sensor_descriptions_have_valid_keys(self, mock_coordinator):
        """Ensure every sensor description key exists in the mock dashboard data."""
        for desc in SENSOR_DESCRIPTIONS:
            sensor = HondaSensor(mock_coordinator, desc, MOCK_VIN, MOCK_VEHICLE_NAME)
            sensor.hass = MagicMock()
            _ = sensor.native_value

    def test_dynamic_unit_distance_km(self, mock_coordinator):
        sensor = make_sensor(mock_coordinator, "range_climate_on")
        assert sensor.native_unit_of_measurement == "km"

    def test_dynamic_unit_speed_km(self, mock_coordinator):
        sensor = make_sensor(mock_coordinator, "speed")
        assert sensor.native_unit_of_measurement == "km/h"

    def test_dynamic_unit_temp_km(self, mock_coordinator):
        sensor = make_sensor(mock_coordinator, "cabin_temp")
        assert sensor.native_unit_of_measurement == "°C"

    def test_dynamic_unit_distance_miles(self, mock_coordinator):
        mock_coordinator.data.distance_unit = "miles"
        sensor = make_sensor(mock_coordinator, "range_climate_on")
        assert sensor.native_unit_of_measurement == "mi"

    def test_dynamic_unit_speed_miles(self, mock_coordinator):
        mock_coordinator.data.distance_unit = "miles"
        sensor = make_sensor(mock_coordinator, "speed")
        assert sensor.native_unit_of_measurement == "mph"

    def test_dynamic_unit_temp_independent_of_distance(self, mock_coordinator):
        """UK uses miles but Celsius; temp must follow temp_unit, not distance_unit."""
        mock_coordinator.data.distance_unit = "miles"
        mock_coordinator.data.temp_unit = "c"
        sensor = make_sensor(mock_coordinator, "cabin_temp")
        assert sensor.native_unit_of_measurement == "°C"

    def test_dynamic_unit_temp_fahrenheit(self, mock_coordinator):
        mock_coordinator.data.temp_unit = "f"
        sensor = make_sensor(mock_coordinator, "cabin_temp")
        assert sensor.native_unit_of_measurement == "°F"

    def test_static_unit_not_affected(self, mock_coordinator):
        sensor = make_sensor(mock_coordinator, "battery_level")
        assert sensor.native_unit_of_measurement == "%"

    def test_charge_schedule_active_count(self, mock_coordinator):
        sensor = make_sensor(mock_coordinator, "charge_schedule")
        assert sensor.native_value == 1

    def test_charge_schedule_attributes(self, mock_coordinator):
        sensor = make_sensor(mock_coordinator, "charge_schedule")
        attrs = sensor.extra_state_attributes
        assert "rules" in attrs
        assert len(attrs["rules"]) == 2
        assert attrs["rules"][0]["enabled"] is True
        assert attrs["rules"][0]["start_time"] == "22:00"

    def test_climate_schedule_active_count(self, mock_coordinator):
        sensor = make_sensor(mock_coordinator, "climate_schedule")
        assert sensor.native_value == 1

    def test_climate_schedule_attributes(self, mock_coordinator):
        sensor = make_sensor(mock_coordinator, "climate_schedule")
        attrs = sensor.extra_state_attributes
        assert attrs["rules"][0]["days"] == ["mon", "tue", "wed", "thu", "fri"]

    def test_schedule_no_attributes_for_non_schedule(self, mock_coordinator):
        sensor = make_sensor(mock_coordinator, "battery_level")
        assert sensor.extra_state_attributes is None

    def test_schedule_empty_list(self, mock_coordinator):
        mock_coordinator.data.charge_schedule = []
        sensor = make_sensor(mock_coordinator, "charge_schedule")
        assert sensor.native_value == 0
        assert sensor.extra_state_attributes == {"rules": []}


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

    def test_distance_unit_dynamic_miles(self, mock_trip_coordinator):
        """Trip data is a dict, so distance_unit must be read via .get(), not getattr()."""
        mock_trip_coordinator.data = dict(mock_trip_coordinator.data,
                                          distance_unit="miles",
                                          speed_unit="miles/h")
        sensor = make_trip_sensor(mock_trip_coordinator, "total_distance")
        assert sensor.native_unit_of_measurement == "mi"
