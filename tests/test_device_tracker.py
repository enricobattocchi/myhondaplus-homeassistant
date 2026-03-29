"""Tests for the device_tracker platform."""

from unittest.mock import MagicMock

from custom_components.myhondaplus.device_tracker import HondaDeviceTracker

from .conftest import MOCK_VEHICLE_NAME, MOCK_VIN


def make_tracker(coordinator):
    """Create a HondaDeviceTracker instance."""
    tracker = HondaDeviceTracker(coordinator, MOCK_VIN, MOCK_VEHICLE_NAME)
    tracker.hass = MagicMock()
    return tracker


class TestDeviceTracker:
    def test_latitude(self, mock_coordinator):
        tracker = make_tracker(mock_coordinator)
        mock_coordinator.data["latitude"] = "45.123"
        assert tracker.latitude == 45.123

    def test_longitude(self, mock_coordinator):
        tracker = make_tracker(mock_coordinator)
        mock_coordinator.data["longitude"] = "9.456"
        assert tracker.longitude == 9.456

    def test_latitude_none(self, mock_coordinator):
        tracker = make_tracker(mock_coordinator)
        mock_coordinator.data.pop("latitude", None)
        assert tracker.latitude is None

    def test_longitude_none(self, mock_coordinator):
        tracker = make_tracker(mock_coordinator)
        mock_coordinator.data.pop("longitude", None)
        assert tracker.longitude is None

    def test_latitude_numeric(self, mock_coordinator):
        tracker = make_tracker(mock_coordinator)
        mock_coordinator.data["latitude"] = 45.0
        assert tracker.latitude == 45.0

    def test_source_type(self, mock_coordinator):
        from homeassistant.components.device_tracker import SourceType

        tracker = make_tracker(mock_coordinator)
        assert tracker.source_type == SourceType.GPS

    def test_unique_id(self, mock_coordinator):
        tracker = make_tracker(mock_coordinator)
        assert tracker._attr_unique_id == f"{MOCK_VIN}_vehicle_location"
