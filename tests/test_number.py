"""Tests for the number platform."""

from unittest.mock import MagicMock

import pytest

from custom_components.myhondaplus.number import HondaChargeLimitNumber, NUMBER_DESCRIPTIONS

from .conftest import MOCK_VIN, MOCK_VEHICLE_NAME


def make_number(coordinator, key):
    """Create a HondaChargeLimitNumber for a given key."""
    desc = next(d for d in NUMBER_DESCRIPTIONS if d.key == key)
    number = HondaChargeLimitNumber(coordinator, desc, MOCK_VIN, MOCK_VEHICLE_NAME)
    number.hass = MagicMock()
    number.async_write_ha_state = MagicMock()
    return number


class TestChargeLimitNumber:
    def test_native_value_home(self, mock_coordinator):
        number = make_number(mock_coordinator, "charge_limit_home")
        assert number.native_value == 90.0

    def test_native_value_away(self, mock_coordinator):
        number = make_number(mock_coordinator, "charge_limit_away")
        assert number.native_value == 100.0

    def test_native_value_none(self, mock_coordinator):
        mock_coordinator.data = {}
        number = make_number(mock_coordinator, "charge_limit_home")
        assert number.native_value is None

    def test_assumed_state_false(self, mock_coordinator):
        number = make_number(mock_coordinator, "charge_limit_home")
        assert number.assumed_state is False

    @pytest.mark.asyncio
    async def test_set_home_limit(self, mock_coordinator):
        number = make_number(mock_coordinator, "charge_limit_home")
        await number.async_set_native_value(85.0)
        mock_coordinator.async_send_command.assert_awaited_once_with(
            mock_coordinator.api.set_charge_limit, MOCK_VIN, 85, 100,
        )
        # Optimistic update
        assert mock_coordinator.data["charge_limit_home"] == 85

    @pytest.mark.asyncio
    async def test_set_away_limit(self, mock_coordinator):
        number = make_number(mock_coordinator, "charge_limit_away")
        await number.async_set_native_value(95.0)
        mock_coordinator.async_send_command.assert_awaited_once_with(
            mock_coordinator.api.set_charge_limit, MOCK_VIN, 90, 95,
        )
        assert mock_coordinator.data["charge_limit_away"] == 95

    @pytest.mark.asyncio
    async def test_set_limit_uses_current_values_for_other(self, mock_coordinator):
        """Setting home should pass the current away value and vice versa."""
        mock_coordinator.data["charge_limit_home"] = 80
        mock_coordinator.data["charge_limit_away"] = 95
        number = make_number(mock_coordinator, "charge_limit_home")
        await number.async_set_native_value(100.0)
        mock_coordinator.async_send_command.assert_awaited_once_with(
            mock_coordinator.api.set_charge_limit, MOCK_VIN, 100, 95,
        )
