"""Tests for the switch platform."""

from unittest.mock import MagicMock

import pytest

from custom_components.myhondaplus.switch import HondaChargeSwitch, HondaClimateSwitch

from .conftest import MOCK_VEHICLE_NAME, MOCK_VIN


@pytest.fixture
def climate_switch(mock_coordinator):
    """Create a HondaClimateSwitch instance."""
    sw = HondaClimateSwitch(mock_coordinator, MOCK_VIN, MOCK_VEHICLE_NAME)
    sw.hass = MagicMock()
    return sw


@pytest.fixture
def charge_switch(mock_coordinator):
    """Create a HondaChargeSwitch instance."""
    sw = HondaChargeSwitch(mock_coordinator, MOCK_VIN, MOCK_VEHICLE_NAME)
    sw.hass = MagicMock()
    return sw


class TestClimateSwitch:
    def test_is_on_true(self, climate_switch):
        climate_switch.coordinator.data["climate_active"] = True
        assert climate_switch.is_on is True

    def test_is_on_false(self, climate_switch):
        climate_switch.coordinator.data["climate_active"] = False
        assert climate_switch.is_on is False

    def test_is_on_string_active(self, climate_switch):
        climate_switch.coordinator.data["climate_active"] = "active"
        assert climate_switch.is_on is True

    def test_is_on_string_true(self, climate_switch):
        climate_switch.coordinator.data["climate_active"] = "true"
        assert climate_switch.is_on is True

    def test_is_on_string_false(self, climate_switch):
        climate_switch.coordinator.data["climate_active"] = "false"
        assert climate_switch.is_on is False

    def test_is_on_none(self, climate_switch):
        climate_switch.coordinator.data["climate_active"] = None
        assert climate_switch.is_on is None

    def test_is_on_missing_key(self, climate_switch):
        climate_switch.coordinator.data.pop("climate_active", None)
        assert climate_switch.is_on is None

    @pytest.mark.asyncio
    async def test_turn_on(self, climate_switch):
        await climate_switch.async_turn_on()
        climate_switch.coordinator.async_send_command_and_wait.assert_awaited_once_with(
            climate_switch.coordinator.api.remote_climate_start, MOCK_VIN,
        )
        climate_switch.coordinator.async_set_updated_data.assert_called_once()
        data = climate_switch.coordinator.async_set_updated_data.call_args[0][0]
        assert data["climate_active"] is True

    @pytest.mark.asyncio
    async def test_turn_off(self, climate_switch):
        await climate_switch.async_turn_off()
        climate_switch.coordinator.async_send_command_and_wait.assert_awaited_once_with(
            climate_switch.coordinator.api.remote_climate_stop, MOCK_VIN,
        )
        climate_switch.coordinator.async_set_updated_data.assert_called_once()
        data = climate_switch.coordinator.async_set_updated_data.call_args[0][0]
        assert data["climate_active"] is False


class TestChargeSwitch:
    def test_is_on_charging(self, charge_switch):
        charge_switch.coordinator.data["charge_status"] = "charging"
        assert charge_switch.is_on is True

    def test_is_on_running(self, charge_switch):
        charge_switch.coordinator.data["charge_status"] = "running"
        assert charge_switch.is_on is True

    def test_is_on_not_charging(self, charge_switch):
        charge_switch.coordinator.data["charge_status"] = "not_charging"
        assert charge_switch.is_on is False

    def test_is_on_unknown(self, charge_switch):
        charge_switch.coordinator.data["charge_status"] = "unknown"
        assert charge_switch.is_on is False

    def test_is_on_none(self, charge_switch):
        charge_switch.coordinator.data["charge_status"] = None
        assert charge_switch.is_on is None

    def test_is_on_missing_key(self, charge_switch):
        charge_switch.coordinator.data.pop("charge_status", None)
        assert charge_switch.is_on is None

    def test_is_on_case_insensitive(self, charge_switch):
        charge_switch.coordinator.data["charge_status"] = "CHARGING"
        assert charge_switch.is_on is True

        charge_switch.coordinator.data["charge_status"] = "Running"
        assert charge_switch.is_on is True

    @pytest.mark.asyncio
    async def test_turn_on(self, charge_switch):
        await charge_switch.async_turn_on()
        charge_switch.coordinator.async_send_command_and_wait.assert_awaited_once_with(
            charge_switch.coordinator.api.remote_charge_start, MOCK_VIN,
        )
        charge_switch.coordinator.async_set_updated_data.assert_called_once()
        data = charge_switch.coordinator.async_set_updated_data.call_args[0][0]
        assert data["charge_status"] == "charging"

    @pytest.mark.asyncio
    async def test_turn_off(self, charge_switch):
        await charge_switch.async_turn_off()
        charge_switch.coordinator.async_send_command_and_wait.assert_awaited_once_with(
            charge_switch.coordinator.api.remote_charge_stop, MOCK_VIN,
        )
        charge_switch.coordinator.async_set_updated_data.assert_called_once()
        data = charge_switch.coordinator.async_set_updated_data.call_args[0][0]
        assert data["charge_status"] == "not_charging"

    @pytest.mark.asyncio
    async def test_turn_on_does_not_mutate_original(self, charge_switch):
        """Ensure optimistic update creates a copy, not mutating coordinator.data."""
        original_data = charge_switch.coordinator.data
        await charge_switch.async_turn_on()
        # The original dict should not have been modified
        assert original_data["charge_status"] == "not_charging"
