"""Tests for the coordinator."""

from collections import namedtuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed
from pymyhondaplus.api import HondaAPIError

from custom_components.myhondaplus.coordinator import (
    HondaDataUpdateCoordinator,
    HondaTripCoordinator,
)

from .conftest import MOCK_DASHBOARD_DATA, MOCK_ENTRY_DATA, MOCK_VIN

Tokens = namedtuple("Tokens", ["access_token", "refresh_token"])


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    hass.config_entries = MagicMock()
    return hass


@pytest.fixture
def mock_entry():
    entry = MagicMock()
    entry.data = dict(MOCK_ENTRY_DATA)
    return entry


@pytest.fixture
def coordinator(mock_hass, mock_entry):
    with patch.object(HondaDataUpdateCoordinator, "__init__", lambda self, *a, **kw: None):
        coord = HondaDataUpdateCoordinator.__new__(HondaDataUpdateCoordinator)
        coord.hass = mock_hass
        coord.entry = mock_entry
        coord.vin = MOCK_VIN
        coord.api = MagicMock()
        coord.api.tokens = Tokens("fake-access-token", "fake-refresh-token")
        coord.data = dict(MOCK_DASHBOARD_DATA)
        coord.logger = MagicMock()
        return coord


@pytest.fixture
def trip_coordinator(mock_hass, mock_entry):
    with patch.object(HondaTripCoordinator, "__init__", lambda self, *a, **kw: None):
        coord = HondaTripCoordinator.__new__(HondaTripCoordinator)
        coord.hass = mock_hass
        coord.entry = mock_entry
        coord.vin = MOCK_VIN
        coord.api = MagicMock()
        coord.api.tokens = Tokens("fake-access-token", "fake-refresh-token")
        coord._persist_tokens = MagicMock()
        coord._fuel_type = "E"
        coord.data = {"trips": 10, "total_km": 200}
        coord.logger = MagicMock()
        return coord


class TestHondaDataUpdateCoordinator:
    @pytest.mark.asyncio
    async def test_update_success(self, coordinator):
        coordinator.hass.async_add_executor_job.return_value = dict(MOCK_DASHBOARD_DATA)
        result = await coordinator._async_update_data()
        assert result["battery_level"] == 75

    @pytest.mark.asyncio
    async def test_update_401_raises_auth_failed(self, coordinator):
        coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(401, "Unauthorized")
        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_update_502_returns_cached_data(self, coordinator):
        coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(502, "Bad Gateway")
        result = await coordinator._async_update_data()
        assert result == coordinator.data

    @pytest.mark.asyncio
    async def test_update_500_returns_cached_data(self, coordinator):
        coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(500, "Internal Server Error")
        result = await coordinator._async_update_data()
        assert result == coordinator.data

    @pytest.mark.asyncio
    async def test_update_503_returns_cached_data(self, coordinator):
        coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(503, "Service Unavailable")
        result = await coordinator._async_update_data()
        assert result == coordinator.data

    @pytest.mark.asyncio
    async def test_update_500_no_cached_data_raises(self, coordinator):
        coordinator.data = None
        coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(500, "Internal Server Error")
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_update_400_raises_update_failed(self, coordinator):
        coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(400, "Bad Request")
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_update_generic_exception_raises(self, coordinator):
        coordinator.hass.async_add_executor_job.side_effect = RuntimeError("boom")
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_refresh_from_car_success(self, coordinator):
        coordinator.hass.async_add_executor_job.return_value = None
        await coordinator.async_refresh_from_car()
        coordinator.hass.async_add_executor_job.assert_awaited_once_with(
            coordinator.api.request_dashboard_refresh, MOCK_VIN,
        )

    @pytest.mark.asyncio
    async def test_refresh_from_car_401(self, coordinator):
        coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(401, "Unauthorized")
        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator.async_refresh_from_car()

    @pytest.mark.asyncio
    async def test_refresh_from_car_502(self, coordinator):
        coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(502, "Bad Gateway")
        with pytest.raises(HomeAssistantError, match="Refresh failed"):
            await coordinator.async_refresh_from_car()

    @pytest.mark.asyncio
    async def test_send_command_success(self, coordinator):
        func = MagicMock()
        coordinator.hass.async_add_executor_job.return_value = "ok"
        result = await coordinator.async_send_command(func, "arg1", "arg2")
        assert result == "ok"
        coordinator.hass.async_add_executor_job.assert_awaited_once_with(func, "arg1", "arg2")

    @pytest.mark.asyncio
    async def test_send_command_401(self, coordinator):
        func = MagicMock()
        coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(401, "Unauthorized")
        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator.async_send_command(func)

    @pytest.mark.asyncio
    async def test_send_command_500(self, coordinator):
        func = MagicMock()
        coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(500, "Error")
        with pytest.raises(HomeAssistantError, match="Command failed"):
            await coordinator.async_send_command(func)


class TestHondaTripCoordinator:
    @pytest.mark.asyncio
    async def test_update_success(self, trip_coordinator):
        trip_coordinator.hass.async_add_executor_job.return_value = {"trips": 5}
        result = await trip_coordinator._async_update_data()
        assert result == {"trips": 5}

    @pytest.mark.asyncio
    async def test_update_401_raises_auth_failed(self, trip_coordinator):
        trip_coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(401, "Unauthorized")
        with pytest.raises(ConfigEntryAuthFailed):
            await trip_coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_update_502_returns_cached_data(self, trip_coordinator):
        trip_coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(502, "Bad Gateway")
        result = await trip_coordinator._async_update_data()
        assert result == trip_coordinator.data

    @pytest.mark.asyncio
    async def test_update_500_no_cached_data_raises(self, trip_coordinator):
        trip_coordinator.data = None
        trip_coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(500, "Error")
        with pytest.raises(UpdateFailed):
            await trip_coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_update_400_raises_update_failed(self, trip_coordinator):
        trip_coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(400, "Bad Request")
        with pytest.raises(UpdateFailed):
            await trip_coordinator._async_update_data()
