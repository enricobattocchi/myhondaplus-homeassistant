"""Tests for the button platform."""

from unittest.mock import MagicMock

import pytest

from custom_components.myhondaplus.button import BUTTON_DESCRIPTIONS, HondaButton

from .conftest import MOCK_VEHICLE_NAME, MOCK_VIN


def make_button(coordinator, key):
    """Create a HondaButton for a given key."""
    desc = next(d for d in BUTTON_DESCRIPTIONS if d.key == key)
    button = HondaButton(coordinator, desc, MOCK_VIN, MOCK_VEHICLE_NAME)
    button.hass = MagicMock()
    return button


class TestHondaButton:
    @pytest.mark.asyncio
    async def test_horn_lights(self, mock_coordinator):
        button = make_button(mock_coordinator, "horn_lights")
        await button.async_press()
        mock_coordinator.async_send_command_and_wait.assert_awaited_once_with(
            mock_coordinator.api.remote_horn_lights, MOCK_VIN,
        )

    @pytest.mark.asyncio
    async def test_refresh_data(self, mock_coordinator):
        button = make_button(mock_coordinator, "refresh_data")
        await button.async_press()
        mock_coordinator.async_refresh_from_car.assert_awaited_once()
