"""Targeted coverage tests for helpers and platform edge cases."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol
from homeassistant.const import PERCENTAGE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityDescription
from pymyhondaplus.api import HondaAPIError

from custom_components.myhondaplus import (
    _schedule_car_refresh,
    _schedule_location_refresh,
    _validate_days,
    _validate_time,
    async_unload_entry,
)
from custom_components.myhondaplus.binary_sensor import (
    async_setup_entry as binary_sensor_setup_entry,
)
from custom_components.myhondaplus.button import (
    BUTTON_DESCRIPTIONS,
    HondaButton,
)
from custom_components.myhondaplus.button import (
    async_setup_entry as button_setup_entry,
)
from custom_components.myhondaplus.coordinator import (
    HondaDataUpdateCoordinator,
    HondaTripCoordinator,
)
from custom_components.myhondaplus.device_tracker import (
    _dms_to_decimal,
)
from custom_components.myhondaplus.device_tracker import (
    async_setup_entry as device_tracker_setup_entry,
)
from custom_components.myhondaplus.entity import MyHondaPlusEntity, to_bool
from custom_components.myhondaplus.lock import async_setup_entry as lock_setup_entry
from custom_components.myhondaplus.number import (
    NUMBER_DESCRIPTIONS,
    HondaChargeLimitNumber,
)
from custom_components.myhondaplus.number import (
    async_setup_entry as number_setup_entry,
)
from custom_components.myhondaplus.select import (
    HondaClimateDurationSelect,
    HondaClimateTempSelect,
)
from custom_components.myhondaplus.select import (
    async_setup_entry as select_setup_entry,
)
from custom_components.myhondaplus.sensor import (
    SENSOR_DESCRIPTIONS,
    TRIP_SENSOR_DESCRIPTIONS,
    HondaSensor,
    HondaTripSensor,
    _resolve_unit,
)
from custom_components.myhondaplus.sensor import (
    async_setup_entry as sensor_setup_entry,
)
from custom_components.myhondaplus.switch import (
    HondaAutoRefreshSwitch,
    HondaChargeSwitch,
    HondaClimateSwitch,
    HondaDefrostSwitch,
)
from custom_components.myhondaplus.switch import (
    async_setup_entry as switch_setup_entry,
)

from .conftest import (
    MOCK_DASHBOARD_DATA,
    MOCK_ENTRY_DATA,
    MOCK_VEHICLE_NAME,
    MOCK_VIN,
)


def _make_hass_mock():
    """Return a MagicMock for hass that properly closes unawaited coroutines."""
    hass = MagicMock()
    hass.async_create_task = lambda coro: coro.close()
    return hass


def make_base_entity(coordinator, key="test_key", vehicle_name=MOCK_VEHICLE_NAME):
    desc = EntityDescription(key=key)
    entity = MyHondaPlusEntity(coordinator, desc, MOCK_VIN, vehicle_name)
    entity.hass = _make_hass_mock()
    return entity


def make_button(coordinator, key):
    desc = next(d for d in BUTTON_DESCRIPTIONS if d.key == key)
    entity = HondaButton(coordinator, desc, MOCK_VIN, MOCK_VEHICLE_NAME)
    entity.hass = _make_hass_mock()
    return entity


def make_number(coordinator, key):
    desc = next(d for d in NUMBER_DESCRIPTIONS if d.key == key)
    entity = HondaChargeLimitNumber(coordinator, desc, MOCK_VIN, MOCK_VEHICLE_NAME)
    entity.hass = _make_hass_mock()
    return entity


def make_sensor(coordinator, key):
    desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == key)
    entity = HondaSensor(coordinator, desc, MOCK_VIN, MOCK_VEHICLE_NAME)
    entity.hass = _make_hass_mock()
    return entity


def make_trip_sensor(coordinator, key):
    desc = next(d for d in TRIP_SENSOR_DESCRIPTIONS if d.key == key)
    entity = HondaTripSensor(coordinator, desc, MOCK_VIN, MOCK_VEHICLE_NAME)
    entity.hass = _make_hass_mock()
    return entity


class TestHelpers:
    def test_validate_days_non_string(self):
        with pytest.raises(vol.Invalid):
            _validate_days(123)

    def test_validate_days_empty(self):
        with pytest.raises(vol.Invalid):
            _validate_days(" , ")

    def test_validate_time_non_string(self):
        with pytest.raises(vol.Invalid):
            _validate_time(123)

    def test_to_bool_numeric(self):
        assert to_bool(1) is True
        assert to_bool(0) is False

    def test_dms_to_decimal_invalid_inputs(self):
        assert _dms_to_decimal({}) is None
        assert _dms_to_decimal("not-a-number") is None
        assert _dms_to_decimal("1,2,boom") is None


class TestEntityHelpers:
    @pytest.mark.asyncio
    async def test_schedule_refresh_replaces_existing_timer(self, mock_coordinator):
        entity = make_base_entity(mock_coordinator)
        old_unsub = MagicMock()
        entity._refresh_unsub = old_unsub
        new_unsub = MagicMock()
        with patch("custom_components.myhondaplus.entity.async_call_later", return_value=new_unsub) as call_later:
            entity._schedule_refresh(15)
        old_unsub.assert_called_once()
        call_later.assert_called_once()
        assert entity._refresh_unsub is new_unsub

    @pytest.mark.asyncio
    async def test_async_will_remove_from_hass_cancels_timer(self, mock_coordinator):
        entity = make_base_entity(mock_coordinator)
        unsub = MagicMock()
        entity._refresh_unsub = unsub
        with patch("homeassistant.helpers.update_coordinator.CoordinatorEntity.async_will_remove_from_hass", AsyncMock()) as super_remove:
            await entity.async_will_remove_from_hass()
        unsub.assert_called_once()
        assert entity._refresh_unsub is None
        super_remove.assert_awaited_once()

    def test_do_refresh_creates_task(self, mock_coordinator):
        entity = make_base_entity(mock_coordinator)
        entity.hass = MagicMock()
        entity.hass.async_create_task = MagicMock(side_effect=lambda coro: coro.close())
        entity._refresh_unsub = MagicMock()
        entity._do_refresh(None)
        assert entity._refresh_unsub is None
        entity.hass.async_create_task.assert_called_once()


class TestButtonCoverage:
    @pytest.mark.asyncio
    async def test_button_platform_setup_entry(self):
        coordinator = SimpleNamespace(entry=SimpleNamespace(data=dict(MOCK_ENTRY_DATA)))
        entry = SimpleNamespace(
            runtime_data=SimpleNamespace(coordinator=coordinator),
            data=dict(MOCK_ENTRY_DATA),
        )
        added = []

        await button_setup_entry(None, entry, added.extend)

        assert len(added) == len(BUTTON_DESCRIPTIONS)
        assert {entity.entity_description.key for entity in added} == {
            description.key for description in BUTTON_DESCRIPTIONS
        }


class TestPlatformSetupCoverage:
    @pytest.mark.asyncio
    async def test_binary_sensor_platform_setup_entry(self):
        coordinator = SimpleNamespace(entry=SimpleNamespace(data=dict(MOCK_ENTRY_DATA)))
        entry = SimpleNamespace(
            runtime_data=SimpleNamespace(coordinator=coordinator),
            data=dict(MOCK_ENTRY_DATA),
        )
        added = []

        await binary_sensor_setup_entry(None, entry, added.extend)

        assert len(added) == 5

    @pytest.mark.asyncio
    async def test_device_tracker_platform_setup_entry(self):
        coordinator = SimpleNamespace(entry=SimpleNamespace(data=dict(MOCK_ENTRY_DATA)))
        entry = SimpleNamespace(
            runtime_data=SimpleNamespace(coordinator=coordinator),
            data=dict(MOCK_ENTRY_DATA),
        )
        added = []

        await device_tracker_setup_entry(None, entry, added.extend)

        assert len(added) == 1
        assert added[0]._vin == MOCK_VIN

    @pytest.mark.asyncio
    async def test_lock_platform_setup_entry(self):
        coordinator = SimpleNamespace(entry=SimpleNamespace(data=dict(MOCK_ENTRY_DATA)))
        entry = SimpleNamespace(
            runtime_data=SimpleNamespace(coordinator=coordinator),
            data=dict(MOCK_ENTRY_DATA),
        )
        added = []

        await lock_setup_entry(None, entry, added.extend)

        assert len(added) == 1
        assert added[0]._vehicle_name == MOCK_VEHICLE_NAME

    @pytest.mark.asyncio
    async def test_number_platform_setup_entry(self):
        coordinator = SimpleNamespace(entry=SimpleNamespace(data=dict(MOCK_ENTRY_DATA)))
        entry = SimpleNamespace(
            runtime_data=SimpleNamespace(coordinator=coordinator),
            data=dict(MOCK_ENTRY_DATA),
        )
        added = []

        await number_setup_entry(None, entry, added.extend)

        assert len(added) == len(NUMBER_DESCRIPTIONS)

    @pytest.mark.asyncio
    async def test_select_platform_setup_entry(self):
        coordinator = SimpleNamespace(entry=SimpleNamespace(data=dict(MOCK_ENTRY_DATA)))
        entry = SimpleNamespace(
            runtime_data=SimpleNamespace(coordinator=coordinator),
            data=dict(MOCK_ENTRY_DATA),
        )
        added = []

        await select_setup_entry(None, entry, added.extend)

        assert len(added) == 2

    @pytest.mark.asyncio
    async def test_sensor_platform_setup_entry(self):
        coordinator = SimpleNamespace(entry=SimpleNamespace(data=dict(MOCK_ENTRY_DATA)))
        trip_coordinator = SimpleNamespace(entry=SimpleNamespace(data=dict(MOCK_ENTRY_DATA)))
        entry = SimpleNamespace(
            runtime_data=SimpleNamespace(
                coordinator=coordinator,
                trip_coordinator=trip_coordinator,
            ),
            data=dict(MOCK_ENTRY_DATA),
        )
        added = []

        await sensor_setup_entry(None, entry, added.extend)

        assert len(added) == len(SENSOR_DESCRIPTIONS) + len(TRIP_SENSOR_DESCRIPTIONS)

    @pytest.mark.asyncio
    async def test_switch_platform_setup_entry(self):
        coordinator = SimpleNamespace(entry=SimpleNamespace(data=dict(MOCK_ENTRY_DATA)))
        entry = SimpleNamespace(
            runtime_data=SimpleNamespace(coordinator=coordinator),
            data=dict(MOCK_ENTRY_DATA),
        )
        added = []

        await switch_setup_entry(None, entry, added.extend)

        assert len(added) == 4


class TestNumberCoverage:
    @pytest.mark.asyncio
    async def test_set_limit_no_update_on_failure(self):
        class FakeCoordinator:
            def __init__(self) -> None:
                self.data = dict(MOCK_DASHBOARD_DATA)
                self.api = SimpleNamespace(set_charge_limit=MagicMock())
                self.entry = SimpleNamespace(data=dict(MOCK_ENTRY_DATA))
                self.async_set_updated_data = MagicMock()

            async def async_send_command_and_wait(self, *args):
                return False

        coordinator = FakeCoordinator()
        description = next(d for d in NUMBER_DESCRIPTIONS if d.key == "charge_limit_home")
        number = HondaChargeLimitNumber(
            coordinator, description, MOCK_VIN, MOCK_VEHICLE_NAME,
        )
        await number.async_set_native_value(85)
        coordinator.async_set_updated_data.assert_not_called()


class TestSelectCoverage:
    @pytest.mark.asyncio
    async def test_temp_select_uses_default_duration_on_invalid_value(self):
        coordinator = SimpleNamespace(
            data={**MOCK_DASHBOARD_DATA, "climate_duration": 99},
            api=SimpleNamespace(set_climate_settings=MagicMock()),
            entry=SimpleNamespace(data=dict(MOCK_ENTRY_DATA)),
            async_send_command_and_wait=AsyncMock(return_value=True),
            async_set_updated_data=MagicMock(),
        )
        entity = HondaClimateTempSelect(coordinator, MOCK_VIN, MOCK_VEHICLE_NAME)
        entity.hass = SimpleNamespace(async_create_task=lambda coro: coro.close())
        await entity.async_select_option("cooler")
        args = coordinator.async_send_command_and_wait.call_args[0]
        assert args[3] == 30

    @pytest.mark.asyncio
    async def test_duration_select_uses_default_temp_on_invalid_value(self):
        coordinator = SimpleNamespace(
            data={**MOCK_DASHBOARD_DATA, "climate_temp": "weird"},
            api=SimpleNamespace(set_climate_settings=MagicMock()),
            entry=SimpleNamespace(data=dict(MOCK_ENTRY_DATA)),
            async_send_command_and_wait=AsyncMock(return_value=True),
            async_set_updated_data=MagicMock(),
        )
        entity = HondaClimateDurationSelect(coordinator, MOCK_VIN, MOCK_VEHICLE_NAME)
        entity.hass = SimpleNamespace(async_create_task=lambda coro: coro.close())
        await entity.async_select_option("10")
        args = coordinator.async_send_command_and_wait.call_args[0]
        assert args[2] == "normal"


class TestSwitchCoverage:
    @pytest.mark.asyncio
    async def test_climate_switch_no_update_on_failure(self, mock_coordinator):
        mock_coordinator.async_send_command_and_wait.return_value = False
        entity = HondaClimateSwitch(mock_coordinator, MOCK_VIN, MOCK_VEHICLE_NAME)
        entity.hass = _make_hass_mock()
        await entity.async_turn_on()
        mock_coordinator.async_set_updated_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_charge_switch_bool_and_failure_paths(self, mock_coordinator):
        entity = HondaChargeSwitch(mock_coordinator, MOCK_VIN, MOCK_VEHICLE_NAME)
        entity.hass = _make_hass_mock()
        mock_coordinator.data["charge_status"] = True
        assert entity.is_on is True
        mock_coordinator.async_send_command_and_wait.return_value = False
        await entity.async_turn_off()
        mock_coordinator.async_set_updated_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_defrost_switch_defaults_and_no_update_on_failure(self, mock_coordinator):
        mock_coordinator.data["climate_temp"] = "bad"
        mock_coordinator.data["climate_duration"] = 99
        mock_coordinator.async_send_command_and_wait.return_value = False
        entity = HondaDefrostSwitch(mock_coordinator, MOCK_VIN, MOCK_VEHICLE_NAME)
        entity.hass = _make_hass_mock()
        await entity.async_turn_off()
        args = mock_coordinator.async_send_command_and_wait.call_args[0]
        assert args[2] == "normal"
        assert args[3] == 30
        mock_coordinator.async_set_updated_data.assert_not_called()

    def test_auto_refresh_switch(self, mock_coordinator):
        entry = MagicMock()
        entry.runtime_data = SimpleNamespace(car_refresh_enabled=False)
        entity = HondaAutoRefreshSwitch(mock_coordinator, MOCK_VIN, MOCK_VEHICLE_NAME, entry)
        entity.async_write_ha_state = MagicMock()
        assert entity.is_on is False

    @pytest.mark.asyncio
    async def test_auto_refresh_switch_toggle(self, mock_coordinator):
        entry = MagicMock()
        entry.runtime_data = SimpleNamespace(car_refresh_enabled=False)
        entity = HondaAutoRefreshSwitch(mock_coordinator, MOCK_VIN, MOCK_VEHICLE_NAME, entry)
        entity.async_write_ha_state = MagicMock()
        await entity.async_turn_on()
        assert entity.is_on is True
        await entity.async_turn_off()
        assert entity.is_on is False
        assert entity.async_write_ha_state.call_count == 2


class TestSensorCoverage:
    def test_resolve_unit_defaults_and_unknown(self):
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "battery_level")
        assert _resolve_unit({}, desc) == PERCENTAGE

    def test_sensor_timestamp_parsing(self, mock_coordinator):
        entity = make_sensor(mock_coordinator, "timestamp")
        assert entity.native_value.year == 2026
        mock_coordinator.data["timestamp"] = "bad"
        assert entity.native_value is None

    def test_sensor_schedule_non_list(self, mock_coordinator):
        mock_coordinator.data["charge_schedule"] = "bad"
        entity = make_sensor(mock_coordinator, "charge_schedule")
        assert entity.native_value == 0
        assert entity.extra_state_attributes is None

    def test_trip_sensor_consumption_and_resolve_unit(self, mock_trip_coordinator):
        entity = make_trip_sensor(mock_trip_coordinator, "total_distance")
        assert entity.native_unit_of_measurement == "km"
        mock_trip_coordinator.data = {"avg_consumption": 12.3, "consumption_unit": "kWh/100km"}
        entity = make_trip_sensor(mock_trip_coordinator, "avg_consumption")
        assert entity.native_unit_of_measurement == "kWh/100km"


class TestCoordinatorCoverage:
    @pytest.mark.asyncio
    async def test_send_command_and_wait_false_command_id(self):
        coord = HondaDataUpdateCoordinator.__new__(HondaDataUpdateCoordinator)
        coord.async_send_command = AsyncMock(return_value="")
        result = await HondaDataUpdateCoordinator.async_send_command_and_wait(coord, MagicMock())
        assert result is False

    @pytest.mark.asyncio
    async def test_send_command_and_wait_unsuccessful_logs_warning(self):
        coord = HondaDataUpdateCoordinator.__new__(HondaDataUpdateCoordinator)
        coord.async_send_command = AsyncMock(return_value="cmd")
        coord.hass = MagicMock()
        coord.api = MagicMock()
        coord._vehicle_name = MOCK_VEHICLE_NAME
        coord.hass.async_add_executor_job = AsyncMock(
            return_value=SimpleNamespace(
                success=False, status="timeout", timed_out=True, reason=None,
            ),
        )
        with patch("custom_components.myhondaplus.coordinator.LOGGER") as logger:
            with patch("custom_components.myhondaplus.coordinator.pn_async_create"):
                result = await HondaDataUpdateCoordinator.async_send_command_and_wait(coord, MagicMock())
        assert result is False
        logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_command_and_wait_timeout_without_notification(self):
        coord = HondaDataUpdateCoordinator.__new__(HondaDataUpdateCoordinator)
        coord.async_send_command = AsyncMock(return_value="cmd")
        coord.hass = MagicMock()
        coord.api = MagicMock()
        coord._vehicle_name = MOCK_VEHICLE_NAME
        coord.hass.async_add_executor_job = AsyncMock(
            return_value=SimpleNamespace(
                success=False, status="timeout", timed_out=True, reason=None,
            ),
        )
        with patch("custom_components.myhondaplus.coordinator.pn_async_create") as pn_create:
            result = await HondaDataUpdateCoordinator.async_send_command_and_wait(
                coord, MagicMock(), notify_on_timeout=False,
            )
        assert result is False
        pn_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_location_api_failure_raises(self):
        coord = HondaDataUpdateCoordinator.__new__(HondaDataUpdateCoordinator)
        coord.vin = MOCK_VIN
        coord.hass = MagicMock()
        coord.api = MagicMock()
        coord._persist_tokens_if_changed = MagicMock()
        coord.async_send_command = AsyncMock(return_value="cmd")
        coord.hass.async_add_executor_job = AsyncMock(side_effect=HondaAPIError(500, "boom"))
        with pytest.raises(HomeAssistantError):
            await HondaDataUpdateCoordinator.async_refresh_location(coord)

    def test_apply_tokens_and_persist_tokens(self):
        coord = HondaDataUpdateCoordinator.__new__(HondaDataUpdateCoordinator)
        coord.entry = MagicMock()
        coord.entry.data = dict(MOCK_ENTRY_DATA)
        coord.hass = MagicMock()
        coord.api = MagicMock()
        coord.api.tokens = SimpleNamespace(
            access_token="new-access",
            refresh_token="new-refresh",
        )
        HondaDataUpdateCoordinator._apply_tokens(coord)
        coord.api.set_tokens.assert_called_once()
        HondaDataUpdateCoordinator._persist_tokens_if_changed(coord)
        coord.hass.config_entries.async_update_entry.assert_called_once()

    def test_fetch_data_and_refresh_command(self):
        coord = HondaDataUpdateCoordinator.__new__(HondaDataUpdateCoordinator)
        coord.vin = MOCK_VIN
        coord.api = MagicMock()
        with patch("custom_components.myhondaplus.coordinator.parse_ev_status", return_value={"x": 1}), \
             patch("custom_components.myhondaplus.coordinator.parse_charge_schedule", return_value=["a"]), \
             patch("custom_components.myhondaplus.coordinator.parse_climate_schedule", return_value=["b"]):
            coord.api.get_dashboard_cached.return_value = {"dash": 1}
            coord.api.refresh_dashboard.return_value = SimpleNamespace(success=True)
            assert HondaDataUpdateCoordinator._fetch_data(coord) == {"x": 1, "charge_schedule": ["a"], "climate_schedule": ["b"]}
            assert HondaDataUpdateCoordinator._refresh_from_car(coord).success is True

    def test_trip_fetch_data_uses_main_coordinator_distance(self):
        coord = HondaTripCoordinator.__new__(HondaTripCoordinator)
        coord.vin = MOCK_VIN
        coord.api = MagicMock()
        coord._fuel_type = "E"
        coord._main_coordinator = MagicMock(data={"distance_unit": "miles"})
        with patch("custom_components.myhondaplus.coordinator.compute_trip_stats", return_value={"ok": True}) as compute:
            coord.api.get_all_trips.return_value = []
            result = HondaTripCoordinator._fetch_data(coord)
        assert result == {"ok": True}
        assert compute.call_args.kwargs["distance_unit"] == "miles"


class TestSchedulerCoverage:
    def test_schedule_car_refresh_disabled(self):
        hass = MagicMock()
        entry = MagicMock()
        entry.options = {"car_refresh_interval": 0}
        entry.runtime_data = SimpleNamespace(coordinator=MagicMock(), car_refresh_enabled=True, car_refresh_unsub=None)
        _schedule_car_refresh(hass, entry)
        assert entry.runtime_data.car_refresh_unsub is None

    def test_schedule_location_refresh_disabled(self):
        hass = MagicMock()
        entry = MagicMock()
        entry.options = {"location_refresh_interval": 0}
        entry.runtime_data = SimpleNamespace(coordinator=MagicMock(), location_refresh_unsub=None)
        _schedule_location_refresh(hass, entry)
        assert entry.runtime_data.location_refresh_unsub is None

    @pytest.mark.asyncio
    async def test_async_unload_entry_with_unsubs(self):
        hass = MagicMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        car_unsub = MagicMock()
        loc_unsub = MagicMock()
        entry = MagicMock()
        entry.runtime_data = SimpleNamespace(
            car_refresh_unsub=car_unsub,
            location_refresh_unsub=loc_unsub,
        )
        assert await async_unload_entry(hass, entry) is True
        car_unsub.assert_called_once()
        loc_unsub.assert_called_once()
