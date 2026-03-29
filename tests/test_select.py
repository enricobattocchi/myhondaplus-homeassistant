"""Tests for the select platform."""

from unittest.mock import MagicMock

import pytest

from custom_components.myhondaplus.select import (
    HondaClimateDurationSelect,
    HondaClimateTempSelect,
)

from .conftest import MOCK_VEHICLE_NAME, MOCK_VIN


@pytest.fixture
def temp_select(mock_coordinator):
    select = HondaClimateTempSelect(mock_coordinator, MOCK_VIN, MOCK_VEHICLE_NAME)
    select.hass = MagicMock()
    return select


@pytest.fixture
def duration_select(mock_coordinator):
    select = HondaClimateDurationSelect(mock_coordinator, MOCK_VIN, MOCK_VEHICLE_NAME)
    select.hass = MagicMock()
    return select


class TestClimateTempSelect:
    def test_options(self, temp_select):
        assert temp_select._attr_options == ["cooler", "normal", "hotter"]

    def test_current_option_normal(self, temp_select):
        temp_select.coordinator.data["climate_temp"] = "normal"
        assert temp_select.current_option == "normal"

    def test_current_option_cooler(self, temp_select):
        temp_select.coordinator.data["climate_temp"] = "cooler"
        assert temp_select.current_option == "cooler"

    def test_current_option_hotter(self, temp_select):
        temp_select.coordinator.data["climate_temp"] = "hotter"
        assert temp_select.current_option == "hotter"

    def test_current_option_invalid_defaults_normal(self, temp_select):
        temp_select.coordinator.data["climate_temp"] = "unknown"
        assert temp_select.current_option == "normal"

    def test_current_option_missing_defaults_normal(self, temp_select):
        temp_select.coordinator.data.pop("climate_temp", None)
        assert temp_select.current_option == "normal"

    @pytest.mark.asyncio
    async def test_select_option_sends_command(self, temp_select):
        await temp_select.async_select_option("hotter")
        temp_select.coordinator.async_send_command_and_wait.assert_awaited_once()
        args = temp_select.coordinator.async_send_command_and_wait.call_args[0]
        assert args[0] is temp_select.coordinator.api.set_climate_settings
        assert args[2] == "hotter"

    @pytest.mark.asyncio
    async def test_select_option_updates_data(self, temp_select):
        await temp_select.async_select_option("cooler")
        temp_select.coordinator.async_set_updated_data.assert_called_once()
        updated = temp_select.coordinator.async_set_updated_data.call_args[0][0]
        assert updated["climate_temp"] == "cooler"

    @pytest.mark.asyncio
    async def test_select_option_no_update_on_timeout(self, temp_select):
        temp_select.coordinator.async_send_command_and_wait.return_value = False
        await temp_select.async_select_option("hotter")
        temp_select.coordinator.async_set_updated_data.assert_not_called()


class TestClimateDurationSelect:
    def test_options(self, duration_select):
        assert duration_select._attr_options == ["10", "20", "30"]

    def test_current_option_30(self, duration_select):
        duration_select.coordinator.data["climate_duration"] = 30
        assert duration_select.current_option == "30"

    def test_current_option_10(self, duration_select):
        duration_select.coordinator.data["climate_duration"] = 10
        assert duration_select.current_option == "10"

    def test_current_option_invalid_defaults_30(self, duration_select):
        duration_select.coordinator.data["climate_duration"] = 99
        assert duration_select.current_option == "30"

    def test_current_option_missing_defaults_30(self, duration_select):
        duration_select.coordinator.data.pop("climate_duration", None)
        assert duration_select.current_option == "30"

    @pytest.mark.asyncio
    async def test_select_option_sends_command(self, duration_select):
        await duration_select.async_select_option("20")
        duration_select.coordinator.async_send_command_and_wait.assert_awaited_once()
        args = duration_select.coordinator.async_send_command_and_wait.call_args[0]
        assert args[0] is duration_select.coordinator.api.set_climate_settings
        assert args[3] == 20

    @pytest.mark.asyncio
    async def test_select_option_updates_data(self, duration_select):
        await duration_select.async_select_option("10")
        duration_select.coordinator.async_set_updated_data.assert_called_once()
        updated = duration_select.coordinator.async_set_updated_data.call_args[0][0]
        assert updated["climate_duration"] == 10

    @pytest.mark.asyncio
    async def test_select_option_no_update_on_timeout(self, duration_select):
        duration_select.coordinator.async_send_command_and_wait.return_value = False
        await duration_select.async_select_option("20")
        duration_select.coordinator.async_set_updated_data.assert_not_called()
