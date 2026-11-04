"""Tests for diagnostics."""

import json
from dataclasses import replace
from unittest.mock import MagicMock

import pytest
from pymyhondaplus.api import Geofence

from custom_components.myhondaplus.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_KEY_PEM,
    CONF_PERSONAL_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_ID,
    CONF_VEHICLE_NAME,
    CONF_VEHICLES,
    CONF_VIN,
)
from custom_components.myhondaplus.diagnostics import (
    TO_REDACT,
    async_get_config_entry_diagnostics,
)

from .conftest import (
    MOCK_DASHBOARD_DATA,
    MOCK_ENTRY_DATA,
    MOCK_TRIP_DATA,
    MOCK_VEHICLE_NAME,
    MOCK_VIN,
)

REDACTED = "**REDACTED**"


@pytest.fixture
def mock_entry_for_diag(mock_runtime_data):
    entry = MagicMock()
    entry.as_dict.return_value = {
        "title": "My Honda+ (test@example.com)",
        "unique_id": "test@example.com",
        "data": dict(MOCK_ENTRY_DATA),
    }
    entry.runtime_data = mock_runtime_data
    # Set realistic data on the vehicle's coordinators
    entry.runtime_data.vehicles[MOCK_VIN].coordinator.data = replace(
        MOCK_DASHBOARD_DATA,
        geofence=Geofence(active=True, latitude=45.5, longitude=9.5, radius=1.0),
    )
    entry.runtime_data.vehicles[MOCK_VIN].trip_coordinator.data = dict(MOCK_TRIP_DATA)
    return entry


class TestDiagnostics:
    def test_redact_set_contains_sensitive_keys(self):
        assert CONF_ACCESS_TOKEN in TO_REDACT
        assert CONF_REFRESH_TOKEN in TO_REDACT
        assert CONF_DEVICE_KEY_PEM in TO_REDACT
        assert CONF_PERSONAL_ID in TO_REDACT
        assert CONF_USER_ID in TO_REDACT
        assert "email" in TO_REDACT
        assert "password" in TO_REDACT
        for key in (
            CONF_VEHICLE_NAME,
            CONF_VIN,
            "latitude",
            "longitude",
            "title",
            "unique_id",
        ):
            assert key in TO_REDACT

    @pytest.mark.asyncio
    async def test_returns_expected_structure(self, mock_entry_for_diag):
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(hass, mock_entry_for_diag)
        assert "config_entry" in result
        assert "vehicles" in result
        assert list(result["vehicles"]) == ["vehicle_1"]
        assert "coordinator_data" in result["vehicles"]["vehicle_1"]
        assert "trip_data" in result["vehicles"]["vehicle_1"]

    @pytest.mark.asyncio
    async def test_coordinator_data_included(self, mock_entry_for_diag):
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(hass, mock_entry_for_diag)
        assert result["vehicles"]["vehicle_1"]["coordinator_data"]["battery_level"] == 75

    @pytest.mark.asyncio
    async def test_trip_data_included(self, mock_entry_for_diag):
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(hass, mock_entry_for_diag)
        assert result["vehicles"]["vehicle_1"]["trip_data"]["trips"] == 15

    @pytest.mark.asyncio
    async def test_sensitive_fields_redacted(self, mock_entry_for_diag):
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(hass, mock_entry_for_diag)
        config = result["config_entry"]
        assert config["title"] == REDACTED
        assert config["unique_id"] == REDACTED
        for key in TO_REDACT:
            if key in config["data"]:
                assert config["data"][key] == REDACTED

    @pytest.mark.asyncio
    async def test_vehicle_identity_redacted(self, mock_entry_for_diag):
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(hass, mock_entry_for_diag)
        vehicle = result["config_entry"]["data"][CONF_VEHICLES][0]
        assert vehicle[CONF_VIN] == REDACTED
        assert vehicle[CONF_VEHICLE_NAME] == REDACTED

    @pytest.mark.asyncio
    async def test_location_redacted(self, mock_entry_for_diag):
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(hass, mock_entry_for_diag)
        dashboard = result["vehicles"]["vehicle_1"]["coordinator_data"]
        assert dashboard["latitude"] == REDACTED
        assert dashboard["longitude"] == REDACTED
        assert dashboard["geofence"]["latitude"] == REDACTED
        assert dashboard["geofence"]["longitude"] == REDACTED
        assert dashboard["geofence"]["radius"] == 1.0

    @pytest.mark.asyncio
    async def test_no_personal_data_in_serialized_output(self, mock_entry_for_diag):
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(hass, mock_entry_for_diag)
        serialized = json.dumps(result)
        for secret in ("test@example.com", MOCK_VIN, MOCK_VEHICLE_NAME):
            assert secret not in serialized

    @pytest.mark.asyncio
    async def test_coordinator_data_none(self, mock_entry_for_diag):
        mock_entry_for_diag.runtime_data.vehicles[MOCK_VIN].coordinator.data = None
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(hass, mock_entry_for_diag)
        assert result["vehicles"]["vehicle_1"]["coordinator_data"] is None

    @pytest.mark.asyncio
    async def test_capabilities_included(self, mock_entry_for_diag):
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(hass, mock_entry_for_diag)
        caps = result["vehicles"]["vehicle_1"]["capabilities"]
        # raw map is the load-bearing field for debugging — must be present
        assert "raw" in caps
        # known per-field booleans should round-trip alongside raw
        assert "remote_charge" in caps
        assert "remote_climate" in caps
        assert "geo_fence" in caps

    @pytest.mark.asyncio
    async def test_ui_config_included(self, mock_entry_for_diag):
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(hass, mock_entry_for_diag)
        ui = result["vehicles"]["vehicle_1"]["ui_config"]
        assert "hide_window_status" in ui
        assert "hide_internal_temperature" in ui

    @pytest.mark.asyncio
    async def test_trip_data_none_when_coordinator_skipped(self, mock_entry_for_diag):
        """Issue #33: trip_data is None when journey_history capability is not Active."""
        mock_entry_for_diag.runtime_data.vehicles[MOCK_VIN].trip_coordinator = None
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(hass, mock_entry_for_diag)
        assert result["vehicles"]["vehicle_1"]["trip_data"] is None
