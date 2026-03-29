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

from .conftest import MOCK_DASHBOARD_DATA, MOCK_ENTRY_DATA, MOCK_TRIP_DATA


@pytest.fixture
def mock_entry_for_diag(mock_coordinator, mock_trip_coordinator):
    entry = MagicMock()
    entry.as_dict.return_value = dict(MOCK_ENTRY_DATA)
    entry.runtime_data = MagicMock()
    entry.runtime_data.coordinator = mock_coordinator
    entry.runtime_data.coordinator.data = dict(MOCK_DASHBOARD_DATA)
    entry.runtime_data.trip_coordinator = mock_trip_coordinator
    entry.runtime_data.trip_coordinator.data = dict(MOCK_TRIP_DATA)
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
        assert "coordinator_data" in result
        assert "trip_data" in result

    @pytest.mark.asyncio
    async def test_coordinator_data_included(self, mock_entry_for_diag):
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(hass, mock_entry_for_diag)
        assert result["coordinator_data"]["battery_level"] == 75

    @pytest.mark.asyncio
    async def test_trip_data_included(self, mock_entry_for_diag):
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(hass, mock_entry_for_diag)
        assert result["trip_data"]["trips"] == 15

    @pytest.mark.asyncio
    async def test_sensitive_fields_redacted(self, mock_entry_for_diag):
        hass = MagicMock()
        result = await async_get_config_entry_diagnostics(hass, mock_entry_for_diag)
        config = result["config_entry"]
        for key in TO_REDACT:
            if key in config:
                assert config[key] == "**REDACTED**"
