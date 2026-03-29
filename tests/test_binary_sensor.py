"""Tests for the binary_sensor platform."""

from unittest.mock import MagicMock

from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from custom_components.myhondaplus.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    HondaBinarySensor,
)

from .conftest import MOCK_VEHICLE_NAME, MOCK_VIN


def make_binary_sensor(coordinator, key):
    """Create a HondaBinarySensor for a given key."""
    desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == key)
    sensor = HondaBinarySensor(coordinator, desc, MOCK_VIN, MOCK_VEHICLE_NAME)
    sensor.hass = MagicMock()
    return sensor


class TestDoorsBinarySensor:
    def test_is_on_when_doors_open(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "doors_open")
        mock_coordinator.data["all_doors_closed"] = False
        assert sensor.is_on is True

    def test_is_off_when_doors_closed(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "doors_open")
        mock_coordinator.data["all_doors_closed"] = True
        assert sensor.is_on is False

    def test_device_class(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "doors_open")
        assert sensor.device_class == BinarySensorDeviceClass.DOOR

    def test_none_when_missing(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "doors_open")
        mock_coordinator.data.pop("all_doors_closed", None)
        assert sensor.is_on is None


class TestWindowsBinarySensor:
    def test_is_on_when_windows_open(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "windows_open")
        mock_coordinator.data["all_windows_closed"] = False
        assert sensor.is_on is True

    def test_is_off_when_windows_closed(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "windows_open")
        mock_coordinator.data["all_windows_closed"] = True
        assert sensor.is_on is False

    def test_device_class(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "windows_open")
        assert sensor.device_class == BinarySensorDeviceClass.WINDOW


class TestHoodBinarySensor:
    def test_is_on_when_hood_open(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "hood")
        mock_coordinator.data["hood_open"] = True
        assert sensor.is_on is True

    def test_is_off_when_hood_closed(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "hood")
        mock_coordinator.data["hood_open"] = False
        assert sensor.is_on is False

    def test_device_class(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "hood")
        assert sensor.device_class == BinarySensorDeviceClass.OPENING


class TestTrunkBinarySensor:
    def test_is_on_when_trunk_open(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "trunk")
        mock_coordinator.data["trunk_open"] = True
        assert sensor.is_on is True

    def test_is_off_when_trunk_closed(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "trunk")
        mock_coordinator.data["trunk_open"] = False
        assert sensor.is_on is False


class TestLightsBinarySensor:
    def test_is_on_when_lights_on(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "lights")
        mock_coordinator.data["lights_on"] = True
        assert sensor.is_on is True

    def test_is_off_when_lights_off(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "lights")
        mock_coordinator.data["lights_on"] = False
        assert sensor.is_on is False

    def test_device_class(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "lights")
        assert sensor.device_class == BinarySensorDeviceClass.LIGHT


class TestStringCoercion:
    """Boolean values might come as strings from the API."""

    def test_string_true(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "hood")
        mock_coordinator.data["hood_open"] = "true"
        assert sensor.is_on is True

    def test_string_false(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "hood")
        mock_coordinator.data["hood_open"] = "false"
        assert sensor.is_on is False

    def test_inverted_string_true(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "doors_open")
        mock_coordinator.data["all_doors_closed"] = "true"
        assert sensor.is_on is False  # inverted: closed=true means NOT open

    def test_inverted_string_false(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "doors_open")
        mock_coordinator.data["all_doors_closed"] = "false"
        assert sensor.is_on is True  # inverted: closed=false means open
