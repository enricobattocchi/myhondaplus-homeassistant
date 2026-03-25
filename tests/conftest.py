"""Shared fixtures for My Honda+ tests."""

from __future__ import annotations

from collections import namedtuple
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.myhondaplus.const import (
    CONF_ACCESS_TOKEN,
    CONF_FUEL_TYPE,
    CONF_PERSONAL_ID,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_USER_ID,
    CONF_VEHICLE_NAME,
    CONF_VIN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

MOCK_VIN = "ZHWGE11S00LA00001"
MOCK_VEHICLE_NAME = "Honda e Test"

MOCK_ENTRY_DATA = {
    CONF_VIN: MOCK_VIN,
    CONF_VEHICLE_NAME: MOCK_VEHICLE_NAME,
    CONF_ACCESS_TOKEN: "fake-access-token",
    CONF_REFRESH_TOKEN: "fake-refresh-token",
    CONF_USER_ID: "fake-user-id",
    CONF_PERSONAL_ID: "fake-personal-id",
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
    CONF_FUEL_TYPE: "E",
}

MOCK_DASHBOARD_DATA = {
    "battery_level": 75,
    "range": 150,
    "total_range": 150,
    "distance_unit": "km",
    "speed_unit": "km/h",
    "temp_unit": "c",
    "charge_status": "not_charging",
    "plug_status": "connected",
    "home_away": "home",
    "charge_limit_home": 90,
    "charge_limit_away": 100,
    "climate_active": False,
    "cabin_temp": 22,
    "interior_temp": 21,
    "odometer": 12345,
    "latitude": "45.0",
    "longitude": "9.0",
    "timestamp": "2026-03-24T10:00:00Z",
    "doors_locked": True,
    "all_doors_closed": True,
    "all_windows_closed": True,
    "ignition": "off",
    "speed": 0,
    "charge_mode": "normal",
    "time_to_charge": 0,
    "hood_open": False,
    "trunk_open": False,
    "lights_on": False,
    "headlights": "off",
    "parking_lights": "off",
    "warning_lamps": [],
    "climate_temp": "normal",
    "climate_duration": 30,
    "climate_defrost": True,
    "charge_schedule": [
        {"enabled": True, "days": ["mon", "tue", "wed", "thu", "fri"],
         "location": "home", "start_time": "22:00", "end_time": "06:00"},
        {"enabled": False, "days": [], "location": "home",
         "start_time": "00:00", "end_time": "00:00"},
    ],
    "climate_schedule": [
        {"enabled": True, "days": ["mon", "tue", "wed", "thu", "fri"],
         "start_time": "07:00"},
        {"enabled": False, "days": [], "start_time": "00:00"},
    ],
}

MOCK_TRIP_DATA = {
    "trips": 15,
    "total_distance": 320,
    "total_minutes": 480,
    "avg_consumption": 14.5,
    "consumption_unit": "kWh/100km",
    "distance_unit": "km",
    "speed_unit": "km/h",
}

Tokens = namedtuple("Tokens", ["access_token", "refresh_token"])


@pytest.fixture
def mock_api():
    """Return a mocked HondaAPI."""
    api = MagicMock()
    api.tokens = Tokens(
        access_token="fake-access-token",
        refresh_token="fake-refresh-token",
    )
    api.get_dashboard_cached.return_value = {}
    api.get_all_trips.return_value = []
    api.get_vehicles.return_value = [
        {"vin": MOCK_VIN, "name": MOCK_VEHICLE_NAME, "plate": "AB123CD", "fuel_type": "E"},
    ]
    api.remote_horn_lights.return_value = "ok"
    api.remote_climate_start.return_value = "ok"
    api.remote_climate_stop.return_value = "ok"
    api.remote_charge_start.return_value = "ok"
    api.remote_charge_stop.return_value = "ok"
    api.remote_lock.return_value = "ok"
    api.remote_unlock.return_value = "ok"
    api.set_charge_limit.return_value = "ok"
    api.set_tokens = MagicMock()
    api.request_dashboard_refresh.return_value = None
    return api


@pytest.fixture
def mock_config_entry():
    """Return a mocked ConfigEntry."""
    entry = MagicMock()
    entry.data = dict(MOCK_ENTRY_DATA)
    entry.entry_id = "test_entry_id"
    entry.domain = DOMAIN
    entry.title = MOCK_VEHICLE_NAME
    return entry


@pytest.fixture
def mock_coordinator(mock_api, mock_config_entry):
    """Return a mocked coordinator with realistic data."""
    coordinator = MagicMock()
    coordinator.data = dict(MOCK_DASHBOARD_DATA)
    coordinator.api = mock_api
    coordinator.entry = mock_config_entry
    coordinator.async_request_refresh = AsyncMock()
    coordinator.async_send_command = AsyncMock()
    coordinator.async_refresh_from_car = AsyncMock()
    coordinator.async_set_updated_data = MagicMock()
    return coordinator


@pytest.fixture
def mock_trip_coordinator():
    """Return a mocked trip coordinator with realistic data."""
    coordinator = MagicMock()
    coordinator.data = dict(MOCK_TRIP_DATA)
    coordinator.entry = MagicMock()
    coordinator.entry.data = dict(MOCK_ENTRY_DATA)
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


@pytest.fixture
def mock_hass():
    """Return a minimal mocked HomeAssistant instance."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    hass.async_create_task = MagicMock()
    hass.config_entries = MagicMock()
    return hass
