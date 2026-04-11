"""Tests for diagnostics."""

from unittest.mock import MagicMock

import pytest

from custom_components.myhondaplus.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_KEY_PEM,
    CONF_PERSONAL_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_ID,
)
from custom_components.myhondaplus.diagnostics import (
    TO_REDACT,
    async_get_config_entry_diagnostics,
)

from .conftest import MOCK_DASHBOARD_DATA, MOCK_ENTRY_DATA, MOCK_TRIP_DATA, MOCK_VIN


@pytest.fixture
def mock_entry_for_diag(mock_runtime_data):
    entry = MagicMock()
    entry.as_dict.return_value = dict(MOCK_ENTRY_DATA)
    entry.runtime_data = mock_runtime_data
    # Set realistic data on the vehicle's coordinators
    entry.runtime_data.vehicles[MOCK_VIN].coordinator.data = dict(MOCK_DASHBOARD_DATA)
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

    @pytest.mark.asyncio
    async def test_returns_expected_structure(self, mock_entry_for_diag):
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(hass, mock_entry_for_diag)
        assert "config_entry" in result
        assert "vehicles" in result
        assert MOCK_VIN in result["vehicles"]
        assert "coordinator_data" in result["vehicles"][MOCK_VIN]
        assert "trip_data" in result["vehicles"][MOCK_VIN]

    @pytest.mark.asyncio
    async def test_coordinator_data_included(self, mock_entry_for_diag):
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(hass, mock_entry_for_diag)
        assert result["vehicles"][MOCK_VIN]["coordinator_data"]["battery_level"] == 75

    @pytest.mark.asyncio
    async def test_trip_data_included(self, mock_entry_for_diag):
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(hass, mock_entry_for_diag)
        assert result["vehicles"][MOCK_VIN]["trip_data"]["trips"] == 15

    @pytest.mark.asyncio
    async def test_sensitive_fields_redacted(self, mock_entry_for_diag):
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(hass, mock_entry_for_diag)
        config = result["config_entry"]
        for key in TO_REDACT:
            if key in config:
                assert config[key] == "**REDACTED**"
