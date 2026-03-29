"""Tests for __init__.py (services, setup, unload)."""

from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.myhondaplus import (
    SERVICE_CLIMATE_ON,
    SERVICE_CLIMATE_ON_SCHEMA,
    SERVICE_SET_CHARGE_SCHEDULE,
    SERVICE_SET_CLIMATE_SCHEDULE,
    _get_coordinator,
    _register_services,
)


@pytest.fixture
def mock_hass_with_services():
    """Return a mocked hass with service registration support."""
    hass = MagicMock()
    hass.services.has_service.return_value = False
    hass.services.async_register = MagicMock()
    return hass


@pytest.fixture
def mock_entry_with_coordinator(mock_coordinator):
    """Return a mocked config entry with runtime_data."""
    entry = MagicMock()
    entry.runtime_data = MagicMock()
    entry.runtime_data.coordinator = mock_coordinator
    entry.runtime_data.trip_coordinator = MagicMock()
    entry.runtime_data.car_refresh_unsub = None
    entry.runtime_data.car_refresh_enabled = True
    return entry


class TestGetCoordinator:
    def test_returns_coordinator(self, mock_coordinator):
        hass = MagicMock()
        entry = MagicMock()
        entry.runtime_data = MagicMock()
        entry.runtime_data.coordinator = mock_coordinator
        hass.config_entries.async_entries.return_value = [entry]
        assert _get_coordinator(hass) is mock_coordinator

    def test_raises_when_no_entries(self):
        hass = MagicMock()
        hass.config_entries.async_entries.return_value = []
        with pytest.raises(ValueError, match="No My Honda\\+"):
            _get_coordinator(hass)

    def test_skips_entries_without_runtime_data(self, mock_coordinator):
        hass = MagicMock()
        entry_no_data = MagicMock(spec=[])  # no runtime_data attr
        entry_with_data = MagicMock()
        entry_with_data.runtime_data = MagicMock()
        entry_with_data.runtime_data.coordinator = mock_coordinator
        hass.config_entries.async_entries.return_value = [entry_no_data, entry_with_data]
        assert _get_coordinator(hass) is mock_coordinator


class TestRegisterServices:
    def test_registers_three_services(self, mock_hass_with_services):
        _register_services(mock_hass_with_services)
        assert mock_hass_with_services.services.async_register.call_count == 3

        registered = {
            call[0][1] for call in mock_hass_with_services.services.async_register.call_args_list
        }
        assert registered == {
            SERVICE_SET_CHARGE_SCHEDULE,
            SERVICE_SET_CLIMATE_SCHEDULE,
            SERVICE_CLIMATE_ON,
        }

    def test_idempotent_registration(self, mock_hass_with_services):
        """Second call does not re-register."""
        _register_services(mock_hass_with_services)
        mock_hass_with_services.services.has_service.return_value = True
        _register_services(mock_hass_with_services)
        # Still only 3 calls from the first registration
        assert mock_hass_with_services.services.async_register.call_count == 3


class TestChargeScheduleSchema:
    def test_valid_charge_rule(self):
        from custom_components.myhondaplus import SERVICE_CHARGE_SCHEDULE_SCHEMA

        result = SERVICE_CHARGE_SCHEDULE_SCHEMA({
            "rules": [{
                "days": "mon,tue,wed",
                "location": "home",
                "start_time": "22:00",
                "end_time": "06:00",
            }],
        })
        assert result["rules"][0]["enabled"] is True

    def test_missing_required_field(self):
        from custom_components.myhondaplus import SERVICE_CHARGE_SCHEDULE_SCHEMA

        with pytest.raises(vol.Invalid):
            SERVICE_CHARGE_SCHEDULE_SCHEMA({
                "rules": [{"days": "mon", "start_time": "22:00"}],
            })

    def test_invalid_location(self):
        from custom_components.myhondaplus import SERVICE_CHARGE_SCHEDULE_SCHEMA

        with pytest.raises(vol.Invalid):
            SERVICE_CHARGE_SCHEDULE_SCHEMA({
                "rules": [{
                    "days": "mon",
                    "location": "work",
                    "start_time": "22:00",
                    "end_time": "06:00",
                }],
            })


class TestClimateScheduleSchema:
    def test_valid_climate_rule(self):
        from custom_components.myhondaplus import SERVICE_CLIMATE_SCHEDULE_SCHEMA

        result = SERVICE_CLIMATE_SCHEDULE_SCHEMA({
            "rules": [{"days": "mon,fri", "start_time": "07:00"}],
        })
        assert result["rules"][0]["enabled"] is True

    def test_missing_days(self):
        from custom_components.myhondaplus import SERVICE_CLIMATE_SCHEDULE_SCHEMA

        with pytest.raises(vol.Invalid):
            SERVICE_CLIMATE_SCHEDULE_SCHEMA({
                "rules": [{"start_time": "07:00"}],
            })


class TestClimateOnSchema:
    def test_defaults(self):
        result = SERVICE_CLIMATE_ON_SCHEMA({})
        assert result["temp"] == "normal"
        assert result["duration"] == 30
        assert result["defrost"] is True

    def test_valid_values(self):
        result = SERVICE_CLIMATE_ON_SCHEMA({
            "temp": "cooler",
            "duration": 10,
            "defrost": False,
        })
        assert result["temp"] == "cooler"
        assert result["duration"] == 10
        assert result["defrost"] is False

    def test_invalid_temp(self):
        with pytest.raises(vol.Invalid):
            SERVICE_CLIMATE_ON_SCHEMA({"temp": "freezing"})

    def test_invalid_duration(self):
        with pytest.raises(vol.Invalid):
            SERVICE_CLIMATE_ON_SCHEMA({"duration": 45})


class TestServiceHandlers:
    @pytest.mark.asyncio
    async def test_handle_climate_on(self, mock_hass_with_services, mock_coordinator):
        """climate_on service calls set_climate_settings then remote_climate_start."""
        _register_services(mock_hass_with_services)
        handlers = {
            call[0][1]: call[0][2]
            for call in mock_hass_with_services.services.async_register.call_args_list
        }

        with patch("custom_components.myhondaplus._get_coordinator", return_value=mock_coordinator):
            call = MagicMock()
            call.data = {"temp": "hotter", "duration": 20, "defrost": False}
            await handlers[SERVICE_CLIMATE_ON](call)

        # Should call set_climate_settings then remote_climate_start
        assert mock_coordinator.async_send_command_and_wait.await_count == 2
        calls = mock_coordinator.async_send_command_and_wait.call_args_list
        assert calls[0][0][0] is mock_coordinator.api.set_climate_settings
        assert calls[1][0][0] is mock_coordinator.api.remote_climate_start
        # Verify optimistic update
        mock_coordinator.async_set_updated_data.assert_called_once()
        updated = mock_coordinator.async_set_updated_data.call_args[0][0]
        assert updated["climate_active"] is True
        assert updated["climate_temp"] == "hotter"
        assert updated["climate_duration"] == 20
        assert updated["climate_defrost"] is False

    @pytest.mark.asyncio
    async def test_handle_set_charge_schedule(self, mock_hass_with_services, mock_coordinator):
        """set_charge_schedule calls API and does optimistic update."""
        _register_services(mock_hass_with_services)
        handlers = {
            call[0][1]: call[0][2]
            for call in mock_hass_with_services.services.async_register.call_args_list
        }

        with patch("custom_components.myhondaplus._get_coordinator", return_value=mock_coordinator):
            call = MagicMock()
            call.data = {"rules": [{"days": "mon,tue", "location": "home", "start_time": "22:00", "end_time": "06:00"}]}
            await handlers[SERVICE_SET_CHARGE_SCHEDULE](call)

        mock_coordinator.async_send_command.assert_awaited_once()
        mock_coordinator.async_set_updated_data.assert_called_once()
        updated = mock_coordinator.async_set_updated_data.call_args[0][0]
        assert len(updated["charge_schedule"]) == 1
        assert updated["charge_schedule"][0]["enabled"] is True

    @pytest.mark.asyncio
    async def test_handle_set_climate_schedule(self, mock_hass_with_services, mock_coordinator):
        """set_climate_schedule calls API and does optimistic update."""
        _register_services(mock_hass_with_services)
        handlers = {
            call[0][1]: call[0][2]
            for call in mock_hass_with_services.services.async_register.call_args_list
        }

        with patch("custom_components.myhondaplus._get_coordinator", return_value=mock_coordinator):
            call = MagicMock()
            call.data = {"rules": [{"days": "mon", "start_time": "07:00"}]}
            await handlers[SERVICE_SET_CLIMATE_SCHEDULE](call)

        mock_coordinator.async_send_command.assert_awaited_once()
        mock_coordinator.async_set_updated_data.assert_called_once()
