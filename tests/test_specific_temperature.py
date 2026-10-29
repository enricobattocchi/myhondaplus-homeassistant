"""Tests for numeric climate control on capable vehicles."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
from pymyhondaplus.api import UIConfiguration, VehicleCapabilities

from custom_components.myhondaplus import SERVICE_CLIMATE_ON, _register_services
from custom_components.myhondaplus.coordinator import HondaDataUpdateCoordinator
from custom_components.myhondaplus.number import (
    HondaClimateTemperatureNumber,
    async_setup_entry,
)
from custom_components.myhondaplus.sensor import (
    SENSOR_DESCRIPTIONS,
    _sensor_enabled,
)
from custom_components.myhondaplus.switch import HondaClimateSwitch

from .conftest import MOCK_DASHBOARD_DATA, MOCK_VEHICLE_NAME, MOCK_VIN

LIMITS = UIConfiguration(
    climate_temp_min=16.0,
    climate_temp_max=30.0,
    climate_temp_step=0.5,
    climate_temp_default=22.0,
)


def make_coordinator(ui_config=LIMITS, specific_temperature=True, target=None):
    """Return a coordinator with its real temperature logic."""
    coordinator = HondaDataUpdateCoordinator.__new__(HondaDataUpdateCoordinator)
    coordinator.specific_temperature = specific_temperature
    coordinator.ui_config = ui_config
    coordinator.climate_temperature = None
    coordinator.data = replace(MOCK_DASHBOARD_DATA, climate_target_temp=target)
    coordinator.vin = MOCK_VIN
    coordinator.api = MagicMock()
    coordinator.async_send_command_and_wait = AsyncMock(return_value=True)
    coordinator.async_set_updated_data = MagicMock()
    return coordinator


async def make_number(coordinator, config=LIMITS):
    """Create the climate temperature number through platform setup."""
    vehicle = SimpleNamespace(
        coordinator=coordinator,
        vin=MOCK_VIN,
        vehicle_name=MOCK_VEHICLE_NAME,
        fuel_type="X",
        capabilities=VehicleCapabilities(remote_climate=True, specific_temperature=True),
        ui_config=config,
    )
    entry = SimpleNamespace(runtime_data=SimpleNamespace(vehicles={MOCK_VIN: vehicle}))
    added = []
    await async_setup_entry(None, entry, added.extend)
    if not added:
        return None
    number = added[0]
    number.hass = MagicMock()
    number.async_write_ha_state = MagicMock()
    return number


class TestValidatedTemperature:
    @pytest.mark.parametrize(
        "value, expected",
        [(21.5, 21.5), (21.11111, 21.0), (21.3, 21.5), (16.0, 16.0), (30.0, 30.0)],
    )
    def test_aligns_to_step(self, value, expected):
        assert make_coordinator().validated_climate_temperature(value) == expected

    @pytest.mark.parametrize("value", [15.5, 30.5, 0.0, -1.0, float("nan"), float("inf")])
    def test_rejects_invalid_values(self, value):
        with pytest.raises(ServiceValidationError) as err:
            make_coordinator().validated_climate_temperature(value)
        assert err.value.translation_key == "climate_temperature_out_of_range"

    def test_rejects_vehicle_without_capability(self):
        coordinator = make_coordinator(specific_temperature=False)
        with pytest.raises(ServiceValidationError) as err:
            coordinator.validated_climate_temperature(21.5)
        assert err.value.translation_key == "capability_not_supported"

    def test_keeps_value_without_limits(self):
        coordinator = make_coordinator(UIConfiguration())
        assert coordinator.validated_climate_temperature(21.3) == 21.3


class TestStartTemperature:
    def test_none_without_capability(self):
        coordinator = make_coordinator(specific_temperature=False, target=20.0)
        assert coordinator.climate_start_temperature() is None

    def test_prefers_chosen_temperature(self):
        coordinator = make_coordinator(target=20.0)
        coordinator.climate_temperature = 23.0
        assert coordinator.climate_start_temperature() == 23.0

    def test_then_reported_target(self):
        assert make_coordinator(target=20.0).climate_start_temperature() == 20.0

    def test_then_vehicle_default(self):
        assert make_coordinator().climate_start_temperature() == 22.0

    def test_raises_when_nothing_is_available(self):
        coordinator = make_coordinator(UIConfiguration())
        with pytest.raises(HomeAssistantError) as err:
            coordinator.climate_start_temperature()
        assert err.value.translation_key == "climate_temperature_unavailable"


class TestClimateSwitch:
    async def test_sends_temperature(self):
        coordinator = make_coordinator(target=20.0)
        switch = HondaClimateSwitch(coordinator, MOCK_VIN, MOCK_VEHICLE_NAME)
        await switch.async_turn_on()
        coordinator.async_send_command_and_wait.assert_awaited_once_with(
            coordinator.api.remote_climate_start, MOCK_VIN, 20.0, True
        )
        updated = coordinator.async_set_updated_data.call_args[0][0]
        assert updated.climate_active is True
        assert updated.climate_target_temp == 20.0

    async def test_no_update_when_not_confirmed(self):
        coordinator = make_coordinator(target=20.0)
        coordinator.async_send_command_and_wait.return_value = False
        switch = HondaClimateSwitch(coordinator, MOCK_VIN, MOCK_VEHICLE_NAME)
        await switch.async_turn_on()
        coordinator.async_set_updated_data.assert_not_called()

    async def test_stops_when_no_temperature_is_available(self):
        coordinator = make_coordinator(UIConfiguration())
        switch = HondaClimateSwitch(coordinator, MOCK_VIN, MOCK_VEHICLE_NAME)
        with pytest.raises(HomeAssistantError):
            await switch.async_turn_on()
        coordinator.async_send_command_and_wait.assert_not_awaited()

    async def test_vehicle_without_capability_sends_no_temperature(self):
        coordinator = make_coordinator(specific_temperature=False)
        switch = HondaClimateSwitch(coordinator, MOCK_VIN, MOCK_VEHICLE_NAME)
        await switch.async_turn_on()
        coordinator.async_send_command_and_wait.assert_awaited_once_with(
            coordinator.api.remote_climate_start, MOCK_VIN, None, True
        )


class TestClimateTemperatureNumber:
    async def test_not_created_without_limits(self):
        assert await make_number(make_coordinator(), UIConfiguration()) is None

    async def test_not_created_with_one_limit(self):
        config = UIConfiguration(climate_temp_min=16.0)
        assert await make_number(make_coordinator(), config) is None

    async def test_uses_vehicle_limits(self):
        number = await make_number(make_coordinator())
        assert number.native_min_value == 16.0
        assert number.native_max_value == 30.0
        assert number.native_step == 0.5

    async def test_value_order(self):
        coordinator = make_coordinator()
        number = await make_number(coordinator)
        assert number.native_value == 22.0
        coordinator.data = replace(coordinator.data, climate_target_temp=20.0)
        assert number.native_value == 20.0
        coordinator.climate_temperature = 23.0
        assert number.native_value == 23.0

    async def test_set_value_stays_in_home_assistant(self):
        coordinator = make_coordinator()
        number = await make_number(coordinator)
        await number.async_set_native_value(23.5)
        assert coordinator.climate_temperature == 23.5
        coordinator.async_send_command_and_wait.assert_not_awaited()
        number.async_write_ha_state.assert_called_once()

    @pytest.mark.parametrize(
        "fahrenheit, expected", [(70.0, 21.0), (60.8, 16.0), (86.0, 30.0)]
    )
    async def test_fahrenheit_values_align_to_the_vehicle(self, fahrenheit, expected):
        coordinator = make_coordinator()
        number = await make_number(coordinator)
        number.hass.config.units = US_CUSTOMARY_SYSTEM
        assert number.unit_of_measurement == "°F"
        await number.async_set_native_value(number.convert_to_native_value(fahrenheit))
        assert coordinator.climate_temperature == expected

    async def test_saves_only_a_chosen_temperature(self):
        coordinator = make_coordinator(target=20.0)
        number = await make_number(coordinator)
        assert number.native_value == 20.0
        assert number.extra_restore_state_data.native_value is None
        await number.async_set_native_value(23.5)
        saved = number.extra_restore_state_data
        assert saved.native_value == 23.5
        assert (saved.native_min_value, saved.native_max_value) == (16.0, 30.0)

    @pytest.mark.parametrize(
        "stored, expected", [(24.0, 24.0), (40.0, None), (None, None)]
    )
    async def test_restores_saved_value_inside_limits(self, stored, expected):
        coordinator = make_coordinator()
        coordinator.async_add_listener = MagicMock()
        number = await make_number(coordinator)
        last = SimpleNamespace(native_value=stored)
        with patch.object(
            HondaClimateTemperatureNumber,
            "async_get_last_number_data",
            AsyncMock(return_value=last),
        ):
            await number.async_added_to_hass()
        assert coordinator.climate_temperature == expected

    async def test_restore_without_saved_data(self):
        coordinator = make_coordinator()
        coordinator.async_add_listener = MagicMock()
        number = await make_number(coordinator)
        with patch.object(
            HondaClimateTemperatureNumber,
            "async_get_last_number_data",
            AsyncMock(return_value=None),
        ):
            await number.async_added_to_hass()
        assert coordinator.climate_temperature is None


class TestSensors:
    @pytest.mark.parametrize(
        "capable, key, expected",
        [
            (True, "climate_target_temp", True),
            (True, "climate_temp", False),
            (False, "climate_target_temp", False),
            (False, "climate_temp", True),
            (True, "climate_duration", True),
        ],
    )
    def test_gated_by_capability(self, capable, key, expected):
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == key)
        vehicle = SimpleNamespace(
            fuel_type="X",
            ui_config=UIConfiguration(),
            capabilities=VehicleCapabilities(
                remote_climate=True, specific_temperature=capable
            ),
        )
        assert _sensor_enabled(desc, vehicle) is expected


class TestClimateOnService:
    async def _call(self, coordinator, data):
        hass = MagicMock()
        hass.services.has_service.return_value = False
        _register_services(hass)
        handlers = {c[0][1]: c[0][2] for c in hass.services.async_register.call_args_list}
        call = MagicMock()
        call.data = data
        with patch(
            "custom_components.myhondaplus._get_coordinator", return_value=coordinator
        ):
            await handlers[SERVICE_CLIMATE_ON](call)

    async def test_sends_requested_temperature_without_settings(self):
        coordinator = make_coordinator(target=20.0)
        await self._call(coordinator, {"temperature": 21.5, "defrost": False})
        coordinator.async_send_command_and_wait.assert_awaited_once_with(
            coordinator.api.remote_climate_start, MOCK_VIN, 21.5, False
        )
        updated = coordinator.async_set_updated_data.call_args[0][0]
        assert updated.climate_target_temp == 21.5
        assert updated.climate_defrost is False
        assert coordinator.climate_temperature is None

    async def test_uses_start_temperature_when_not_requested(self):
        coordinator = make_coordinator(target=20.0)
        await self._call(coordinator, {"temp": "normal", "duration": 30})
        coordinator.async_send_command_and_wait.assert_awaited_once_with(
            coordinator.api.remote_climate_start, MOCK_VIN, 20.0, True
        )

    async def test_no_update_when_not_confirmed(self):
        coordinator = make_coordinator(target=20.0)
        coordinator.async_send_command_and_wait.return_value = False
        await self._call(coordinator, {})
        coordinator.async_set_updated_data.assert_not_called()

    async def test_rejects_out_of_range_temperature(self):
        coordinator = make_coordinator()
        with pytest.raises(ServiceValidationError):
            await self._call(coordinator, {"temperature": 40})
        coordinator.async_send_command_and_wait.assert_not_awaited()

    async def test_rejects_temperature_without_capability(self):
        coordinator = make_coordinator(specific_temperature=False)
        with pytest.raises(ServiceValidationError):
            await self._call(coordinator, {"temperature": 21.5})
        coordinator.async_send_command_and_wait.assert_not_awaited()
