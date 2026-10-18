"""Tests for the binary_sensor platform."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from custom_components.myhondaplus.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    HondaBinarySensor,
)
from custom_components.myhondaplus.sensor import SENSOR_DESCRIPTIONS

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
        mock_coordinator.data.all_doors_closed = False
        assert sensor.is_on is True

    def test_is_off_when_doors_closed(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "doors_open")
        mock_coordinator.data.all_doors_closed = True
        assert sensor.is_on is False

    def test_device_class(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "doors_open")
        assert sensor.device_class == BinarySensorDeviceClass.DOOR

    def test_none_when_missing(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "doors_open")
        mock_coordinator.data.all_doors_closed = None
        assert sensor.is_on is None


class TestWindowsBinarySensor:
    def test_is_on_when_windows_open(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "windows_open")
        mock_coordinator.data.all_windows_closed = False
        assert sensor.is_on is True

    def test_is_off_when_windows_closed(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "windows_open")
        mock_coordinator.data.all_windows_closed = True
        assert sensor.is_on is False

    def test_device_class(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "windows_open")
        assert sensor.device_class == BinarySensorDeviceClass.WINDOW


class TestHoodBinarySensor:
    def test_is_on_when_hood_open(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "hood")
        mock_coordinator.data.hood_open = True
        assert sensor.is_on is True

    def test_is_off_when_hood_closed(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "hood")
        mock_coordinator.data.hood_open = False
        assert sensor.is_on is False

    def test_device_class(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "hood")
        assert sensor.device_class == BinarySensorDeviceClass.OPENING


class TestTrunkBinarySensor:
    def test_is_on_when_trunk_open(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "trunk")
        mock_coordinator.data.trunk_open = True
        assert sensor.is_on is True

    def test_is_off_when_trunk_closed(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "trunk")
        mock_coordinator.data.trunk_open = False
        assert sensor.is_on is False


class TestLightsBinarySensor:
    def test_is_on_when_lights_on(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "lights")
        mock_coordinator.data.lights_on = True
        assert sensor.is_on is True

    def test_is_off_when_lights_off(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "lights")
        mock_coordinator.data.lights_on = False
        assert sensor.is_on is False

    def test_device_class(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "lights")
        assert sensor.device_class == BinarySensorDeviceClass.LIGHT


class TestStringCoercion:
    """Boolean values might come as strings from the API."""

    def test_string_true(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "hood")
        mock_coordinator.data.hood_open = "true"
        assert sensor.is_on is True

    def test_string_false(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "hood")
        mock_coordinator.data.hood_open = "false"
        assert sensor.is_on is False

    def test_inverted_string_true(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "doors_open")
        mock_coordinator.data.all_doors_closed = "true"
        assert sensor.is_on is False  # inverted: closed=true means NOT open

    def test_inverted_string_false(self, mock_coordinator):
        sensor = make_binary_sensor(mock_coordinator, "doors_open")
        mock_coordinator.data.all_doors_closed = "false"
        assert sensor.is_on is True  # inverted: closed=false means open


@pytest.mark.parametrize("key", ["climate_active", "climate_defrost", "doors_locked"])
@pytest.mark.parametrize(
    ("value", "expected"),
    [(True, True), (False, False), ("true", True), ("false", False),
     (1, True), (0, False), (None, None)],
)
def test_moved_boolean_states(mock_coordinator, key, value, expected):
    """Keep unknown data unknown and invert lock state for HA semantics."""
    sensor = make_binary_sensor(mock_coordinator, key)
    setattr(mock_coordinator.data, key, value)
    if key == "doors_locked" and expected is not None:
        expected = not expected
    assert sensor.is_on is expected
    assert sensor.unique_id == f"{MOCK_VIN}_{key}"
    assert sensor.device_class == (
        BinarySensorDeviceClass.LOCK if key == "doors_locked"
        else BinarySensorDeviceClass.RUNNING
    )


def test_moved_booleans_are_no_longer_sensors():
    assert not {"climate_active", "climate_defrost", "doors_locked"}.intersection(
        desc.key for desc in SENSOR_DESCRIPTIONS
    )


def test_moved_boolean_translations():
    component = Path(__file__).parent.parent / "custom_components/myhondaplus"
    locales = sorted((component / "translations").glob("*.json"))
    assert len(locales) == 13
    for path in [component / "strings.json", *locales]:
        entity = json.loads(path.read_text())["entity"]
        for key in ("climate_active", "climate_defrost", "doors_locked"):
            assert entity["binary_sensor"][key]["name"]
            assert key not in entity["sensor"]
