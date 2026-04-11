"""Tests for __init__.py (services, setup, unload)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import ServiceValidationError

from custom_components.myhondaplus import (
    ATTR_DEVICE,
    SERVICE_CLIMATE_ON,
    SERVICE_CLIMATE_ON_SCHEMA,
    SERVICE_SET_CHARGE_SCHEDULE,
    SERVICE_SET_CLIMATE_SCHEDULE,
    _consolidate_duplicate_entries,
    _get_coordinator,
    _register_services,
    async_migrate_entry,
    async_reload_entry,
    async_setup,
    async_setup_entry,
)
from custom_components.myhondaplus.const import (
    CONF_ACCESS_TOKEN,
    CONF_CAR_REFRESH_INTERVAL,
    CONF_FUEL_TYPE,
    CONF_LOCATION_REFRESH_INTERVAL,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_USER_ID,
    CONF_VEHICLE_NAME,
    CONF_VEHICLES,
    CONF_VIN,
    DOMAIN,
)
from tests.conftest import MOCK_V2_ENTRY_DATA, MOCK_VIN


@pytest.fixture
def mock_hass_with_services():
    """Return a mocked hass with service registration support."""
    hass = MagicMock()
    hass.services.has_service.return_value = False
    hass.services.async_register = MagicMock()
    return hass


class TestGetCoordinator:
    def test_returns_coordinator_via_device(self, mock_coordinator, mock_runtime_data):
        hass = MagicMock()
        device = MagicMock()
        device.identifiers = {(DOMAIN, MOCK_VIN)}
        entry = MagicMock()
        entry.domain = DOMAIN
        entry.state = ConfigEntryState.LOADED
        entry.runtime_data = mock_runtime_data
        device.config_entries = {"entry_1"}
        hass.config_entries.async_get_entry.return_value = entry

        with patch("custom_components.myhondaplus.dr") as mock_dr:
            mock_dr.async_get.return_value.async_get.return_value = device
            result = _get_coordinator(hass, MagicMock(data={ATTR_DEVICE: "device_1"}))

        assert result is mock_coordinator

    def test_raises_when_no_device(self):
        hass = MagicMock()
        with pytest.raises(ServiceValidationError) as exc_info:
            _get_coordinator(hass, MagicMock(data={}))
        assert exc_info.value.translation_key == "device_required"

    def test_raises_when_device_not_found(self):
        hass = MagicMock()
        with patch("custom_components.myhondaplus.dr") as mock_dr:
            mock_dr.async_get.return_value.async_get.return_value = None
            with pytest.raises(ServiceValidationError) as exc_info:
                _get_coordinator(hass, MagicMock(data={ATTR_DEVICE: "nonexistent"}))
        assert exc_info.value.translation_key == "device_not_found"


class TestRegisterServices:
    @pytest.mark.asyncio
    async def test_async_setup_registers_services(self, mock_hass_with_services):
        assert await async_setup(mock_hass_with_services, {}) is True
        assert mock_hass_with_services.services.async_register.call_count == 3

    def test_registers_three_services(self, mock_hass_with_services):
        _register_services(mock_hass_with_services)
        assert mock_hass_with_services.services.async_register.call_count == 3

        registered = {
            call[0][1]
            for call in mock_hass_with_services.services.async_register.call_args_list
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


class TestMigration:
    @pytest.mark.asyncio
    async def test_migrate_v1_moves_interval_settings_to_options(self, mock_hass):
        entry = MagicMock()
        entry.version = 1
        entry.data = {
            CONF_SCAN_INTERVAL: 300,
            CONF_CAR_REFRESH_INTERVAL: 7200,
            CONF_LOCATION_REFRESH_INTERVAL: 1800,
            "email": "test@example.com",
            "vin": "VIN123",
            "vehicle_name": "Car",
            "fuel_type": "E",
        }
        entry.options = {}
        entry.unique_id = "VIN123"

        # Simulate version advancing after each async_update_entry
        def advance_version(*args, **kwargs):
            entry.version = kwargs.get("version", entry.version)

        mock_hass.config_entries.async_update_entry.side_effect = advance_version

        assert await async_migrate_entry(mock_hass, entry) is True

        # v1→v2 is the first call, v2→v3 is the second
        assert mock_hass.config_entries.async_update_entry.call_count == 2
        first_call = mock_hass.config_entries.async_update_entry.call_args_list[
            0
        ].kwargs
        assert first_call["version"] == 2
        second_call = mock_hass.config_entries.async_update_entry.call_args_list[
            1
        ].kwargs
        assert second_call["version"] == 3
        assert CONF_VEHICLES in second_call["data"]

    @pytest.mark.asyncio
    async def test_migrate_v2_wraps_vehicle_in_list(self, mock_hass):
        entry = MagicMock()
        entry.version = 2
        entry.data = dict(MOCK_V2_ENTRY_DATA)
        entry.options = {}
        entry.unique_id = MOCK_VIN

        assert await async_migrate_entry(mock_hass, entry) is True

        kwargs = mock_hass.config_entries.async_update_entry.call_args.kwargs
        assert CONF_VIN not in kwargs["data"]
        assert CONF_VEHICLE_NAME not in kwargs["data"]
        assert CONF_FUEL_TYPE not in kwargs["data"]
        assert kwargs["data"][CONF_VEHICLES] == [
            {
                CONF_VIN: MOCK_VIN,
                CONF_VEHICLE_NAME: "Honda e Test",
                CONF_FUEL_TYPE: "E",
            }
        ]
        assert kwargs["unique_id"] == "test@example.com"
        assert kwargs["version"] == 3

    @pytest.mark.asyncio
    async def test_migrate_v3_noop(self, mock_hass):
        entry = MagicMock()
        entry.version = 3
        entry.data = {}
        entry.options = {}

        assert await async_migrate_entry(mock_hass, entry) is True
        mock_hass.config_entries.async_update_entry.assert_not_called()


class TestConsolidation:
    def test_merges_duplicate_entries(self, mock_hass):
        """Two entries for the same email get merged."""
        main_entry = MagicMock()
        main_entry.entry_id = "main"
        main_entry.data = {
            "email": "test@example.com",
            CONF_VEHICLES: [
                {CONF_VIN: "VIN1", CONF_VEHICLE_NAME: "Car 1", CONF_FUEL_TYPE: "E"}
            ],
        }

        dup_entry = MagicMock()
        dup_entry.entry_id = "dup"
        dup_entry.data = {
            "email": "test@example.com",
            CONF_VEHICLES: [
                {CONF_VIN: "VIN2", CONF_VEHICLE_NAME: "Car 2", CONF_FUEL_TYPE: "H"}
            ],
        }

        mock_hass.config_entries.async_entries.return_value = [main_entry, dup_entry]

        _consolidate_duplicate_entries(mock_hass, main_entry)

        # Should merge VIN2 into main entry
        update_call = mock_hass.config_entries.async_update_entry.call_args
        new_vehicles = update_call.kwargs["data"][CONF_VEHICLES]
        assert len(new_vehicles) == 2
        assert {v[CONF_VIN] for v in new_vehicles} == {"VIN1", "VIN2"}

        # Should remove duplicate
        mock_hass.async_create_task.assert_called_once()

    def test_no_duplicates_noop(self, mock_hass):
        """Single entry does nothing."""
        entry = MagicMock()
        entry.entry_id = "only"
        entry.data = {
            "email": "test@example.com",
            CONF_VEHICLES: [{CONF_VIN: "VIN1"}],
        }
        mock_hass.config_entries.async_entries.return_value = [entry]

        _consolidate_duplicate_entries(mock_hass, entry)

        mock_hass.config_entries.async_update_entry.assert_not_called()


class TestSetupEntry:
    @pytest.mark.asyncio
    async def test_setup_entry_registers_update_listener(self, mock_hass):
        entry = MagicMock()
        entry.data = {
            "email": "test@example.com",
            CONF_ACCESS_TOKEN: "tok",
            CONF_REFRESH_TOKEN: "ref",
            CONF_USER_ID: "uid",
            CONF_VEHICLES: [
                {CONF_VIN: MOCK_VIN, CONF_VEHICLE_NAME: "Car", CONF_FUEL_TYPE: "E"}
            ],
        }
        entry.options = {}
        entry.entry_id = "test"
        entry.add_update_listener = MagicMock(return_value="listener")
        entry.async_on_unload = MagicMock()
        mock_hass.config_entries.async_forward_entry_setups = AsyncMock(
            return_value=True
        )
        mock_hass.config_entries.async_entries.return_value = [entry]

        with (
            patch("custom_components.myhondaplus.HondaAPI") as api_cls,
            patch(
                "custom_components.myhondaplus.HondaDataUpdateCoordinator"
            ) as coord_cls,
            patch("custom_components.myhondaplus.HondaTripCoordinator") as trip_cls,
            patch("custom_components.myhondaplus._schedule_car_refresh"),
            patch("custom_components.myhondaplus._schedule_location_refresh"),
            patch("custom_components.myhondaplus._cleanup_removed_vehicles"),
        ):
            api_cls.return_value = MagicMock()
            coord = MagicMock()
            coord.async_config_entry_first_refresh = AsyncMock()
            coord._persist_tokens_if_changed = MagicMock()
            coord_cls.return_value = coord
            trip = MagicMock()
            trip.async_config_entry_first_refresh = AsyncMock()
            trip_cls.return_value = trip

            assert await async_setup_entry(mock_hass, entry) is True

        entry.add_update_listener.assert_called_once()
        entry.async_on_unload.assert_called_once_with("listener")

    @pytest.mark.asyncio
    async def test_reload_entry_uses_config_entries_reload(self, mock_hass):
        entry = MagicMock()
        entry.entry_id = "entry_1"
        mock_hass.config_entries.async_reload = AsyncMock()

        await async_reload_entry(mock_hass, entry)

        mock_hass.config_entries.async_reload.assert_awaited_once_with("entry_1")


class TestChargeScheduleSchema:
    def test_valid_charge_rule(self):
        from custom_components.myhondaplus import SERVICE_CHARGE_SCHEDULE_SCHEMA

        result = SERVICE_CHARGE_SCHEDULE_SCHEMA(
            {
                "device": "device_1",
                "rules": [
                    {
                        "days": "mon,tue,wed",
                        "location": "home",
                        "start_time": "22:00",
                        "end_time": "06:00",
                    }
                ],
            }
        )
        assert result["device"] == "device_1"
        assert result["rules"][0]["enabled"] is True

    def test_missing_required_field(self):
        from custom_components.myhondaplus import SERVICE_CHARGE_SCHEDULE_SCHEMA

        with pytest.raises(vol.Invalid):
            SERVICE_CHARGE_SCHEDULE_SCHEMA(
                {
                    "rules": [{"days": "mon", "start_time": "22:00"}],
                }
            )

    def test_invalid_location(self):
        from custom_components.myhondaplus import SERVICE_CHARGE_SCHEDULE_SCHEMA

        with pytest.raises(vol.Invalid):
            SERVICE_CHARGE_SCHEDULE_SCHEMA(
                {
                    "device": "d1",
                    "rules": [
                        {
                            "days": "mon",
                            "location": "work",
                            "start_time": "22:00",
                            "end_time": "06:00",
                        }
                    ],
                }
            )

    def test_invalid_day_token(self):
        from custom_components.myhondaplus import SERVICE_CHARGE_SCHEDULE_SCHEMA

        with pytest.raises(vol.Invalid):
            SERVICE_CHARGE_SCHEDULE_SCHEMA(
                {
                    "device": "d1",
                    "rules": [
                        {
                            "days": "mon,holiday",
                            "location": "home",
                            "start_time": "22:00",
                            "end_time": "06:00",
                        }
                    ],
                }
            )

    def test_duplicate_days(self):
        from custom_components.myhondaplus import SERVICE_CHARGE_SCHEDULE_SCHEMA

        with pytest.raises(vol.Invalid):
            SERVICE_CHARGE_SCHEDULE_SCHEMA(
                {
                    "device": "d1",
                    "rules": [
                        {
                            "days": "mon,mon",
                            "location": "home",
                            "start_time": "22:00",
                            "end_time": "06:00",
                        }
                    ],
                }
            )

    def test_invalid_time(self):
        from custom_components.myhondaplus import SERVICE_CHARGE_SCHEDULE_SCHEMA

        with pytest.raises(vol.Invalid):
            SERVICE_CHARGE_SCHEDULE_SCHEMA(
                {
                    "device": "d1",
                    "rules": [
                        {
                            "days": "mon",
                            "location": "home",
                            "start_time": "25:00",
                            "end_time": "06:00",
                        }
                    ],
                }
            )

    def test_max_two_rules(self):
        from custom_components.myhondaplus import SERVICE_CHARGE_SCHEDULE_SCHEMA

        with pytest.raises(vol.Invalid):
            SERVICE_CHARGE_SCHEDULE_SCHEMA(
                {
                    "device": "d1",
                    "rules": [
                        {
                            "days": "mon",
                            "location": "home",
                            "start_time": "22:00",
                            "end_time": "06:00",
                        },
                        {
                            "days": "tue",
                            "location": "home",
                            "start_time": "22:00",
                            "end_time": "06:00",
                        },
                        {
                            "days": "wed",
                            "location": "home",
                            "start_time": "22:00",
                            "end_time": "06:00",
                        },
                    ],
                }
            )


class TestClimateScheduleSchema:
    def test_valid_climate_rule(self):
        from custom_components.myhondaplus import SERVICE_CLIMATE_SCHEDULE_SCHEMA

        result = SERVICE_CLIMATE_SCHEDULE_SCHEMA(
            {
                "device": "device_1",
                "rules": [{"days": "mon,fri", "start_time": "07:00"}],
            }
        )
        assert result["device"] == "device_1"
        assert result["rules"][0]["enabled"] is True

    def test_missing_days(self):
        from custom_components.myhondaplus import SERVICE_CLIMATE_SCHEDULE_SCHEMA

        with pytest.raises(vol.Invalid):
            SERVICE_CLIMATE_SCHEDULE_SCHEMA(
                {
                    "device": "d1",
                    "rules": [{"start_time": "07:00"}],
                }
            )

    def test_invalid_time(self):
        from custom_components.myhondaplus import SERVICE_CLIMATE_SCHEDULE_SCHEMA

        with pytest.raises(vol.Invalid):
            SERVICE_CLIMATE_SCHEDULE_SCHEMA(
                {
                    "device": "d1",
                    "rules": [{"days": "mon", "start_time": "7:00"}],
                }
            )

    def test_invalid_day_token(self):
        from custom_components.myhondaplus import SERVICE_CLIMATE_SCHEDULE_SCHEMA

        with pytest.raises(vol.Invalid):
            SERVICE_CLIMATE_SCHEDULE_SCHEMA(
                {
                    "device": "d1",
                    "rules": [{"days": "mon,foo", "start_time": "07:00"}],
                }
            )

    def test_max_seven_rules(self):
        from custom_components.myhondaplus import SERVICE_CLIMATE_SCHEDULE_SCHEMA

        with pytest.raises(vol.Invalid):
            SERVICE_CLIMATE_SCHEDULE_SCHEMA(
                {
                    "device": "d1",
                    "rules": [
                        {"days": "mon", "start_time": "07:00"},
                        {"days": "tue", "start_time": "07:00"},
                        {"days": "wed", "start_time": "07:00"},
                        {"days": "thu", "start_time": "07:00"},
                        {"days": "fri", "start_time": "07:00"},
                        {"days": "sat", "start_time": "07:00"},
                        {"days": "sun", "start_time": "07:00"},
                        {"days": "mon", "start_time": "08:00"},
                    ],
                }
            )


class TestClimateOnSchema:
    def test_defaults(self):
        result = SERVICE_CLIMATE_ON_SCHEMA({"device": "device_1"})
        assert result["device"] == "device_1"
        assert result["temp"] == "normal"
        assert result["duration"] == 30
        assert result["defrost"] is True

    def test_valid_values(self):
        result = SERVICE_CLIMATE_ON_SCHEMA(
            {
                "device": "device_1",
                "temp": "cooler",
                "duration": 10,
                "defrost": False,
            }
        )
        assert result["device"] == "device_1"
        assert result["temp"] == "cooler"
        assert result["duration"] == 10
        assert result["defrost"] is False

    def test_valid_string_duration_from_ui(self):
        result = SERVICE_CLIMATE_ON_SCHEMA(
            {
                "device": "device_1",
                "duration": "20",
            }
        )
        assert result["duration"] == 20

    def test_invalid_temp(self):
        with pytest.raises(vol.Invalid):
            SERVICE_CLIMATE_ON_SCHEMA({"device": "d1", "temp": "freezing"})

    def test_invalid_duration(self):
        with pytest.raises(vol.Invalid):
            SERVICE_CLIMATE_ON_SCHEMA({"device": "d1", "duration": 45})


class TestServiceHandlers:
    @pytest.mark.asyncio
    async def test_handle_climate_on(self, mock_hass_with_services, mock_coordinator):
        """climate_on service calls set_climate_settings then remote_climate_start."""
        _register_services(mock_hass_with_services)
        handlers = {
            call[0][1]: call[0][2]
            for call in mock_hass_with_services.services.async_register.call_args_list
        }

        with patch(
            "custom_components.myhondaplus._get_coordinator",
            return_value=mock_coordinator,
        ):
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
    async def test_handle_set_charge_schedule(
        self, mock_hass_with_services, mock_coordinator
    ):
        """set_charge_schedule calls API and does optimistic update."""
        _register_services(mock_hass_with_services)
        handlers = {
            call[0][1]: call[0][2]
            for call in mock_hass_with_services.services.async_register.call_args_list
        }

        with patch(
            "custom_components.myhondaplus._get_coordinator",
            return_value=mock_coordinator,
        ):
            call = MagicMock()
            call.data = {
                "rules": [
                    {
                        "days": "mon,tue",
                        "location": "home",
                        "start_time": "22:00",
                        "end_time": "06:00",
                    }
                ]
            }
            await handlers[SERVICE_SET_CHARGE_SCHEDULE](call)

        mock_coordinator.async_send_command.assert_awaited_once()
        mock_coordinator.async_set_updated_data.assert_called_once()
        updated = mock_coordinator.async_set_updated_data.call_args[0][0]
        assert len(updated["charge_schedule"]) == 1
        assert updated["charge_schedule"][0]["enabled"] is True

    @pytest.mark.asyncio
    async def test_handle_set_climate_schedule(
        self, mock_hass_with_services, mock_coordinator
    ):
        """set_climate_schedule calls API and does optimistic update."""
        _register_services(mock_hass_with_services)
        handlers = {
            call[0][1]: call[0][2]
            for call in mock_hass_with_services.services.async_register.call_args_list
        }

        with patch(
            "custom_components.myhondaplus._get_coordinator",
            return_value=mock_coordinator,
        ):
            call = MagicMock()
            call.data = {"rules": [{"days": "mon", "start_time": "07:00"}]}
            await handlers[SERVICE_SET_CLIMATE_SCHEDULE](call)

        mock_coordinator.async_send_command.assert_awaited_once()
        mock_coordinator.async_set_updated_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_handlers_pass_service_call_to_target_resolution(
        self,
        mock_hass_with_services,
        mock_coordinator,
    ):
        _register_services(mock_hass_with_services)
        handlers = {
            call[0][1]: call[0][2]
            for call in mock_hass_with_services.services.async_register.call_args_list
        }

        call = MagicMock()
        call.data = {
            "rules": [{"days": "mon", "start_time": "07:00"}],
        }
        with patch(
            "custom_components.myhondaplus._get_coordinator",
            return_value=mock_coordinator,
        ) as get_coordinator:
            await handlers[SERVICE_SET_CLIMATE_SCHEDULE](call)

        get_coordinator.assert_called_once_with(mock_hass_with_services, call)
