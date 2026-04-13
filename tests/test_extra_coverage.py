"""Targeted coverage tests for helpers and platform edge cases."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol
from homeassistant.const import PERCENTAGE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityDescription
from pymyhondaplus.api import (
    EVStatus,
    HondaAPIError,
    HondaAuthError,
    UIConfiguration,
    Vehicle,
    VehicleCapabilities,
)

from custom_components.myhondaplus import (
    _build_model_name_from_vehicle,
    _cleanup_removed_vehicles,
    _fetch_vehicle_metadata,
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
from custom_components.myhondaplus.config_flow import MyHondaPlusConfigFlow
from custom_components.myhondaplus.const import (
    CONF_CAR_REFRESH_INTERVAL,
    CONF_LOCATION_REFRESH_INTERVAL,
    CONF_SCAN_INTERVAL,
    DEFAULT_CAR_REFRESH_INTERVAL,
    DEFAULT_LOCATION_REFRESH_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
)
from custom_components.myhondaplus.coordinator import (
    DashboardData,
    HondaDataUpdateCoordinator,
    HondaTripCoordinator,
)
from custom_components.myhondaplus.data import VehicleData
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
    _sensor_enabled,
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


def _make_entry_with_vehicles(coordinator, trip_coordinator=None):
    """Create a mock entry with the new vehicles-based runtime_data."""
    vd = VehicleData(
        coordinator=coordinator,
        trip_coordinator=trip_coordinator or MagicMock(),
        vin=MOCK_VIN,
        vehicle_name=MOCK_VEHICLE_NAME,
        fuel_type="E",
    )
    return SimpleNamespace(
        runtime_data=SimpleNamespace(
            vehicles={MOCK_VIN: vd},
            api=MagicMock(),
        ),
        data=dict(MOCK_ENTRY_DATA),
    )


def make_base_entity(coordinator, key="test_key", vehicle_name=MOCK_VEHICLE_NAME):
    desc = EntityDescription(key=key)
    entity = MyHondaPlusEntity(coordinator, desc, MOCK_VIN, vehicle_name, "E")
    entity.hass = _make_hass_mock()
    return entity


def make_button(coordinator, key):
    desc = next(d for d in BUTTON_DESCRIPTIONS if d.key == key)
    entity = HondaButton(coordinator, desc, MOCK_VIN, MOCK_VEHICLE_NAME, "E")
    entity.hass = _make_hass_mock()
    return entity


def make_number(coordinator, key):
    desc = next(d for d in NUMBER_DESCRIPTIONS if d.key == key)
    entity = HondaChargeLimitNumber(coordinator, desc, MOCK_VIN, MOCK_VEHICLE_NAME, "E")
    entity.hass = _make_hass_mock()
    return entity


def make_sensor(coordinator, key):
    desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == key)
    entity = HondaSensor(coordinator, desc, MOCK_VIN, MOCK_VEHICLE_NAME, "E")
    entity.hass = _make_hass_mock()
    return entity


def make_trip_sensor(coordinator, key):
    desc = next(d for d in TRIP_SENSOR_DESCRIPTIONS if d.key == key)
    entity = HondaTripSensor(coordinator, desc, MOCK_VIN, MOCK_VEHICLE_NAME, "E")
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
        with patch(
            "custom_components.myhondaplus.entity.async_call_later",
            return_value=new_unsub,
        ) as call_later:
            entity._schedule_refresh(15)
        old_unsub.assert_called_once()
        call_later.assert_called_once()
        assert entity._refresh_unsub is new_unsub

    @pytest.mark.asyncio
    async def test_async_will_remove_from_hass_cancels_timer(self, mock_coordinator):
        entity = make_base_entity(mock_coordinator)
        unsub = MagicMock()
        entity._refresh_unsub = unsub
        with patch(
            "homeassistant.helpers.update_coordinator.CoordinatorEntity.async_will_remove_from_hass",
            AsyncMock(),
        ) as super_remove:
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
        entry = _make_entry_with_vehicles(coordinator)
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
        entry = _make_entry_with_vehicles(coordinator)
        added = []

        await binary_sensor_setup_entry(None, entry, added.extend)

        assert len(added) == 5

    @pytest.mark.asyncio
    async def test_device_tracker_platform_setup_entry(self):
        coordinator = SimpleNamespace(entry=SimpleNamespace(data=dict(MOCK_ENTRY_DATA)))
        entry = _make_entry_with_vehicles(coordinator)
        added = []

        await device_tracker_setup_entry(None, entry, added.extend)

        assert len(added) == 1
        assert added[0]._vin == MOCK_VIN

    @pytest.mark.asyncio
    async def test_lock_platform_setup_entry(self):
        coordinator = SimpleNamespace(entry=SimpleNamespace(data=dict(MOCK_ENTRY_DATA)))
        entry = _make_entry_with_vehicles(coordinator)
        added = []

        await lock_setup_entry(None, entry, added.extend)

        assert len(added) == 1
        assert added[0]._vehicle_name == MOCK_VEHICLE_NAME

    @pytest.mark.asyncio
    async def test_number_platform_setup_entry(self):
        coordinator = SimpleNamespace(entry=SimpleNamespace(data=dict(MOCK_ENTRY_DATA)))
        entry = _make_entry_with_vehicles(coordinator)
        added = []

        await number_setup_entry(None, entry, added.extend)

        assert len(added) == len(NUMBER_DESCRIPTIONS)

    @pytest.mark.asyncio
    async def test_select_platform_setup_entry(self):
        coordinator = SimpleNamespace(entry=SimpleNamespace(data=dict(MOCK_ENTRY_DATA)))
        entry = _make_entry_with_vehicles(coordinator)
        added = []

        await select_setup_entry(None, entry, added.extend)

        assert len(added) == 2

    @pytest.mark.asyncio
    async def test_sensor_platform_setup_entry(self):
        coordinator = SimpleNamespace(entry=SimpleNamespace(data=dict(MOCK_ENTRY_DATA)))
        trip_coordinator = SimpleNamespace(
            entry=SimpleNamespace(data=dict(MOCK_ENTRY_DATA))
        )
        entry = _make_entry_with_vehicles(coordinator, trip_coordinator)
        added = []

        await sensor_setup_entry(None, entry, added.extend)

        assert len(added) == len(SENSOR_DESCRIPTIONS) + len(TRIP_SENSOR_DESCRIPTIONS)

    @pytest.mark.asyncio
    async def test_switch_platform_setup_entry(self):
        coordinator = SimpleNamespace(entry=SimpleNamespace(data=dict(MOCK_ENTRY_DATA)))
        entry = _make_entry_with_vehicles(coordinator)
        added = []

        await switch_setup_entry(None, entry, added.extend)

        assert len(added) == 4


class TestNumberCoverage:
    @pytest.mark.asyncio
    async def test_set_limit_no_update_on_failure(self):
        class FakeCoordinator:
            def __init__(self) -> None:
                self.data = replace(MOCK_DASHBOARD_DATA)
                self.api = SimpleNamespace(set_charge_limit=MagicMock())
                self.entry = SimpleNamespace(data=dict(MOCK_ENTRY_DATA))
                self.async_set_updated_data = MagicMock()

            async def async_send_command_and_wait(self, *args):
                return False

        coordinator = FakeCoordinator()
        description = next(
            d for d in NUMBER_DESCRIPTIONS if d.key == "charge_limit_home"
        )
        number = HondaChargeLimitNumber(
            coordinator,
            description,
            MOCK_VIN,
            MOCK_VEHICLE_NAME,
            "E",
        )
        await number.async_set_native_value(85)
        coordinator.async_set_updated_data.assert_not_called()


class TestSelectCoverage:
    @pytest.mark.asyncio
    async def test_temp_select_uses_default_duration_on_invalid_value(self):
        coordinator = SimpleNamespace(
            data=replace(MOCK_DASHBOARD_DATA, climate_duration=99),
            api=SimpleNamespace(set_climate_settings=MagicMock()),
            entry=SimpleNamespace(data=dict(MOCK_ENTRY_DATA)),
            async_send_command_and_wait=AsyncMock(return_value=True),
            async_set_updated_data=MagicMock(),
        )
        entity = HondaClimateTempSelect(coordinator, MOCK_VIN, MOCK_VEHICLE_NAME, "E")
        entity.hass = SimpleNamespace(async_create_task=lambda coro: coro.close())
        await entity.async_select_option("cooler")
        args = coordinator.async_send_command_and_wait.call_args[0]
        assert args[3] == 30

    @pytest.mark.asyncio
    async def test_duration_select_uses_default_temp_on_invalid_value(self):
        coordinator = SimpleNamespace(
            data=replace(MOCK_DASHBOARD_DATA, climate_temp="weird"),
            api=SimpleNamespace(set_climate_settings=MagicMock()),
            entry=SimpleNamespace(data=dict(MOCK_ENTRY_DATA)),
            async_send_command_and_wait=AsyncMock(return_value=True),
            async_set_updated_data=MagicMock(),
        )
        entity = HondaClimateDurationSelect(
            coordinator, MOCK_VIN, MOCK_VEHICLE_NAME, "E"
        )
        entity.hass = SimpleNamespace(async_create_task=lambda coro: coro.close())
        await entity.async_select_option("10")
        args = coordinator.async_send_command_and_wait.call_args[0]
        assert args[2] == "normal"


class TestSwitchCoverage:
    @pytest.mark.asyncio
    async def test_climate_switch_no_update_on_failure(self, mock_coordinator):
        mock_coordinator.async_send_command_and_wait.return_value = False
        entity = HondaClimateSwitch(mock_coordinator, MOCK_VIN, MOCK_VEHICLE_NAME, "E")
        entity.hass = _make_hass_mock()
        await entity.async_turn_on()
        mock_coordinator.async_set_updated_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_charge_switch_bool_and_failure_paths(self, mock_coordinator):
        entity = HondaChargeSwitch(mock_coordinator, MOCK_VIN, MOCK_VEHICLE_NAME, "E")
        entity.hass = _make_hass_mock()
        mock_coordinator.data.charge_status = True
        assert entity.is_on is True
        mock_coordinator.async_send_command_and_wait.return_value = False
        await entity.async_turn_off()
        mock_coordinator.async_set_updated_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_defrost_switch_defaults_and_no_update_on_failure(
        self, mock_coordinator
    ):
        mock_coordinator.data.climate_temp = "bad"
        mock_coordinator.data.climate_duration = 99
        mock_coordinator.async_send_command_and_wait.return_value = False
        entity = HondaDefrostSwitch(mock_coordinator, MOCK_VIN, MOCK_VEHICLE_NAME, "E")
        entity.hass = _make_hass_mock()
        await entity.async_turn_off()
        args = mock_coordinator.async_send_command_and_wait.call_args[0]
        assert args[2] == "normal"
        assert args[3] == 30
        mock_coordinator.async_set_updated_data.assert_not_called()

    def test_auto_refresh_switch(self, mock_coordinator):
        vd = VehicleData(
            coordinator=mock_coordinator,
            trip_coordinator=MagicMock(),
            vin=MOCK_VIN,
            vehicle_name=MOCK_VEHICLE_NAME,
            fuel_type="E",
            car_refresh_enabled=False,
        )
        entity = HondaAutoRefreshSwitch(
            mock_coordinator, MOCK_VIN, MOCK_VEHICLE_NAME, "E", vd
        )
        entity.async_write_ha_state = MagicMock()
        assert entity.is_on is False

    @pytest.mark.asyncio
    async def test_auto_refresh_switch_toggle(self, mock_coordinator):
        vd = VehicleData(
            coordinator=mock_coordinator,
            trip_coordinator=MagicMock(),
            vin=MOCK_VIN,
            vehicle_name=MOCK_VEHICLE_NAME,
            fuel_type="E",
            car_refresh_enabled=False,
        )
        entity = HondaAutoRefreshSwitch(
            mock_coordinator, MOCK_VIN, MOCK_VEHICLE_NAME, "E", vd
        )
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
        mock_coordinator.data.timestamp = "bad"
        assert entity.native_value is None

    def test_sensor_schedule_non_list(self, mock_coordinator):
        mock_coordinator.data.charge_schedule = "bad"
        entity = make_sensor(mock_coordinator, "charge_schedule")
        assert entity.native_value == 0
        assert entity.extra_state_attributes is None

    def test_trip_sensor_consumption_and_resolve_unit(self, mock_trip_coordinator):
        entity = make_trip_sensor(mock_trip_coordinator, "total_distance")
        assert entity.native_unit_of_measurement == "km"
        mock_trip_coordinator.data = {
            "avg_consumption": 12.3,
            "consumption_unit": "kWh/100km",
        }
        entity = make_trip_sensor(mock_trip_coordinator, "avg_consumption")
        assert entity.native_unit_of_measurement == "kWh/100km"


class TestCoordinatorCoverage:
    @pytest.mark.asyncio
    async def test_send_command_and_wait_false_command_id(self):
        coord = HondaDataUpdateCoordinator.__new__(HondaDataUpdateCoordinator)
        coord.async_send_command = AsyncMock(return_value="")
        result = await HondaDataUpdateCoordinator.async_send_command_and_wait(
            coord, MagicMock()
        )
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
                success=False,
                status="timeout",
                timed_out=True,
                reason=None,
            ),
        )
        with patch("custom_components.myhondaplus.coordinator.LOGGER") as logger:
            with patch("custom_components.myhondaplus.coordinator.pn_async_create"):
                result = await HondaDataUpdateCoordinator.async_send_command_and_wait(
                    coord, MagicMock()
                )
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
                success=False,
                status="timeout",
                timed_out=True,
                reason=None,
            ),
        )
        with patch(
            "custom_components.myhondaplus.coordinator.pn_async_create"
        ) as pn_create:
            result = await HondaDataUpdateCoordinator.async_send_command_and_wait(
                coord,
                MagicMock(),
                notify_on_timeout=False,
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
        coord.hass.async_add_executor_job = AsyncMock(
            side_effect=HondaAPIError(500, "boom")
        )
        with pytest.raises(HomeAssistantError):
            await HondaDataUpdateCoordinator.async_refresh_location(coord)

    def test_persist_tokens_is_noop(self):
        """Token persistence is now handled by the library's storage backend."""
        coord = HondaDataUpdateCoordinator.__new__(HondaDataUpdateCoordinator)
        coord.hass = MagicMock()
        HondaDataUpdateCoordinator._persist_tokens_if_changed(coord)
        coord.hass.config_entries.async_update_entry.assert_not_called()


class TestConfigEntryTokenStorage:
    """Tests for _ConfigEntryTokenStorage adapter."""

    def _make_storage(self):
        from custom_components.myhondaplus import _ConfigEntryTokenStorage

        hass = _make_hass_mock()
        entry = MagicMock()
        entry.data = dict(MOCK_ENTRY_DATA)
        storage = _ConfigEntryTokenStorage(hass, entry)
        return storage, hass, entry

    def test_load_tokens_returns_entry_data(self):
        storage, _, entry = self._make_storage()
        result = storage.load_tokens()
        assert result["access_token"] == "fake-access-token"
        assert result["refresh_token"] == "fake-refresh-token"
        assert result["personal_id"] == "fake-personal-id"
        assert result["user_id"] == "fake-user-id"

    def test_load_tokens_returns_none_when_no_access_token(self):
        storage, _, entry = self._make_storage()
        entry.data = {}
        assert storage.load_tokens() is None

    def test_save_tokens_schedules_update_on_event_loop(self):
        storage, hass, entry = self._make_storage()
        storage.save_tokens({
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_at": 9999999.0,
        })
        hass.loop.call_soon_threadsafe.assert_called_once()

    def test_do_update_merges_with_latest_entry_data(self):
        """Token save must use current entry.data, not a stale snapshot."""
        storage, hass, entry = self._make_storage()
        # Simulate _fetch_vehicle_metadata updating entry.data after save_tokens
        # was called but before _do_update runs.
        entry.data = {**MOCK_ENTRY_DATA, "model": "HR-V"}
        token_fields = {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "token_expires_at": 9999999.0,
        }
        storage._do_update(token_fields)
        call_args = hass.config_entries.async_update_entry.call_args
        written_data = call_args.kwargs.get("data", call_args[1].get("data"))
        # Must contain BOTH the model backfill AND the new tokens
        assert written_data["model"] == "HR-V"
        assert written_data["access_token"] == "new-access"
        assert written_data["refresh_token"] == "new-refresh"
        assert written_data["token_expires_at"] == 9999999.0
        # Must preserve other fields
        assert written_data["email"] == "test@example.com"


class TestUpdateListenerFiltering:
    """Tests for the options-only reload behavior."""

    @pytest.mark.asyncio
    async def test_token_only_update_does_not_reload(self):
        """Updating tokens in entry.data must not trigger a reload."""
        from custom_components.myhondaplus import async_setup_entry

        hass = _make_hass_mock()
        entry = MagicMock()
        entry.data = dict(MOCK_ENTRY_DATA)
        entry.options = {
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_CAR_REFRESH_INTERVAL: DEFAULT_CAR_REFRESH_INTERVAL,
            CONF_LOCATION_REFRESH_INTERVAL: DEFAULT_LOCATION_REFRESH_INTERVAL,
        }
        # Capture the update listener callback
        listeners = []
        entry.add_update_listener = MagicMock(side_effect=lambda cb: listeners.append(cb))
        entry.async_on_unload = MagicMock()

        with patch("custom_components.myhondaplus.HondaAPI") as mock_api_cls, \
             patch("custom_components.myhondaplus._fetch_vehicle_metadata", return_value={}), \
             patch("custom_components.myhondaplus._cleanup_removed_vehicles"), \
             patch("custom_components.myhondaplus._schedule_car_refresh"), \
             patch("custom_components.myhondaplus._schedule_location_refresh"), \
             patch("custom_components.myhondaplus._update_device_models"), \
             patch("custom_components.myhondaplus._consolidate_duplicate_entries"):
            mock_api = MagicMock()
            mock_api_cls.return_value = mock_api
            mock_api.tokens = SimpleNamespace(
                access_token="a", refresh_token="r", expires_at=0,
                personal_id="p", user_id="u",
            )
            coordinator = MagicMock()
            coordinator._persist_tokens_if_changed = MagicMock()
            coordinator.async_config_entry_first_refresh = AsyncMock()
            trip_coordinator = MagicMock()
            trip_coordinator.async_config_entry_first_refresh = AsyncMock()
            with patch(
                "custom_components.myhondaplus.HondaDataUpdateCoordinator",
                return_value=coordinator,
            ), patch(
                "custom_components.myhondaplus.HondaTripCoordinator",
                return_value=trip_coordinator,
            ):
                hass.config_entries.async_forward_entry_setups = AsyncMock()
                await async_setup_entry(hass, entry)

        assert len(listeners) == 1
        on_update = listeners[0]

        # Simulate token-only change (options unchanged)
        hass.config_entries.async_reload = AsyncMock()
        await on_update(hass, entry)
        hass.config_entries.async_reload.assert_not_called()

    @pytest.mark.asyncio
    async def test_options_change_triggers_reload(self):
        """Changing options (e.g. scan interval) must trigger a reload."""
        from custom_components.myhondaplus import async_setup_entry

        hass = _make_hass_mock()
        entry = MagicMock()
        entry.data = dict(MOCK_ENTRY_DATA)
        entry.options = {
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_CAR_REFRESH_INTERVAL: DEFAULT_CAR_REFRESH_INTERVAL,
            CONF_LOCATION_REFRESH_INTERVAL: DEFAULT_LOCATION_REFRESH_INTERVAL,
        }
        listeners = []
        entry.add_update_listener = MagicMock(side_effect=lambda cb: listeners.append(cb))
        entry.async_on_unload = MagicMock()

        with patch("custom_components.myhondaplus.HondaAPI") as mock_api_cls, \
             patch("custom_components.myhondaplus._fetch_vehicle_metadata", return_value={}), \
             patch("custom_components.myhondaplus._cleanup_removed_vehicles"), \
             patch("custom_components.myhondaplus._schedule_car_refresh"), \
             patch("custom_components.myhondaplus._schedule_location_refresh"), \
             patch("custom_components.myhondaplus._update_device_models"), \
             patch("custom_components.myhondaplus._consolidate_duplicate_entries"):
            mock_api = MagicMock()
            mock_api_cls.return_value = mock_api
            mock_api.tokens = SimpleNamespace(
                access_token="a", refresh_token="r", expires_at=0,
                personal_id="p", user_id="u",
            )
            coordinator = MagicMock()
            coordinator._persist_tokens_if_changed = MagicMock()
            coordinator.async_config_entry_first_refresh = AsyncMock()
            trip_coordinator = MagicMock()
            trip_coordinator.async_config_entry_first_refresh = AsyncMock()
            with patch(
                "custom_components.myhondaplus.HondaDataUpdateCoordinator",
                return_value=coordinator,
            ), patch(
                "custom_components.myhondaplus.HondaTripCoordinator",
                return_value=trip_coordinator,
            ):
                hass.config_entries.async_forward_entry_setups = AsyncMock()
                await async_setup_entry(hass, entry)

        assert len(listeners) == 1
        on_update = listeners[0]

        # Simulate options change
        entry.options = {
            CONF_SCAN_INTERVAL: 300,  # changed
            CONF_CAR_REFRESH_INTERVAL: DEFAULT_CAR_REFRESH_INTERVAL,
            CONF_LOCATION_REFRESH_INTERVAL: DEFAULT_LOCATION_REFRESH_INTERVAL,
        }
        hass.config_entries.async_reload = AsyncMock()
        await on_update(hass, entry)
        hass.config_entries.async_reload.assert_called_once_with(entry.entry_id)


class TestCoordinatorCoveragePart2:
    """Continuation of coordinator tests (split for readability)."""

    def test_fetch_data_and_refresh_command(self):
        coord = HondaDataUpdateCoordinator.__new__(HondaDataUpdateCoordinator)
        coord.vin = MOCK_VIN
        coord.api = MagicMock()
        mock_ev = EVStatus(battery_level=42)
        with (
            patch(
                "custom_components.myhondaplus.coordinator.parse_ev_status",
                return_value=mock_ev,
            ),
            patch(
                "custom_components.myhondaplus.coordinator.parse_charge_schedule",
                return_value=["a"],
            ),
            patch(
                "custom_components.myhondaplus.coordinator.parse_climate_schedule",
                return_value=["b"],
            ),
        ):
            coord.api.get_dashboard_cached.return_value = {"dash": 1}
            coord.api.refresh_dashboard.return_value = SimpleNamespace(success=True)
            result = HondaDataUpdateCoordinator._fetch_data(coord)
            assert isinstance(result, DashboardData)
            assert result.battery_level == 42
            assert result.charge_schedule == ["a"]
            assert result.climate_schedule == ["b"]
            assert HondaDataUpdateCoordinator._refresh_from_car(coord).success is True

    def test_trip_fetch_data_uses_main_coordinator_distance(self):
        coord = HondaTripCoordinator.__new__(HondaTripCoordinator)
        coord.vin = MOCK_VIN
        coord.api = MagicMock()
        coord._fuel_type = "E"
        coord._main_coordinator = MagicMock(data=replace(MOCK_DASHBOARD_DATA, distance_unit="miles"))
        with patch(
            "custom_components.myhondaplus.coordinator.compute_trip_stats",
            return_value={"ok": True},
        ) as compute:
            coord.api.get_all_trips.return_value = []
            result = HondaTripCoordinator._fetch_data(coord)
        assert result == {"ok": True}
        assert compute.call_args.kwargs["distance_unit"] == "miles"


class TestSchedulerCoverage:
    def test_schedule_car_refresh_disabled(self):
        hass = MagicMock()
        entry = MagicMock()
        entry.options = {"car_refresh_interval": 0}
        vd = VehicleData(
            coordinator=MagicMock(),
            trip_coordinator=MagicMock(),
            vin=MOCK_VIN,
            vehicle_name=MOCK_VEHICLE_NAME,
            fuel_type="E",
        )
        _schedule_car_refresh(hass, entry, vd)
        assert vd.car_refresh_unsub is None

    def test_schedule_location_refresh_disabled(self):
        hass = MagicMock()
        entry = MagicMock()
        entry.options = {"location_refresh_interval": 0}
        vd = VehicleData(
            coordinator=MagicMock(),
            trip_coordinator=MagicMock(),
            vin=MOCK_VIN,
            vehicle_name=MOCK_VEHICLE_NAME,
            fuel_type="E",
        )
        _schedule_location_refresh(hass, entry, vd)
        assert vd.location_refresh_unsub is None

    def test_schedule_car_refresh_enabled(self):
        hass = MagicMock()
        entry = MagicMock()
        entry.options = {"car_refresh_interval": 3600}
        vd = VehicleData(
            coordinator=MagicMock(),
            trip_coordinator=MagicMock(),
            vin=MOCK_VIN,
            vehicle_name=MOCK_VEHICLE_NAME,
            fuel_type="E",
        )
        with patch(
            "custom_components.myhondaplus.async_call_later", return_value=MagicMock()
        ) as call_later:
            _schedule_car_refresh(hass, entry, vd)
        call_later.assert_called_once()
        assert vd.car_refresh_unsub is not None

    def test_schedule_location_refresh_enabled(self):
        hass = MagicMock()
        entry = MagicMock()
        entry.options = {"location_refresh_interval": 3600}
        vd = VehicleData(
            coordinator=MagicMock(),
            trip_coordinator=MagicMock(),
            vin=MOCK_VIN,
            vehicle_name=MOCK_VEHICLE_NAME,
            fuel_type="E",
        )
        with patch(
            "custom_components.myhondaplus.async_call_later", return_value=MagicMock()
        ) as call_later:
            _schedule_location_refresh(hass, entry, vd)
        call_later.assert_called_once()
        assert vd.location_refresh_unsub is not None

    @pytest.mark.asyncio
    async def test_async_unload_entry_with_unsubs(self):
        hass = MagicMock()
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        car_unsub = MagicMock()
        loc_unsub = MagicMock()
        vd = VehicleData(
            coordinator=MagicMock(),
            trip_coordinator=MagicMock(),
            vin=MOCK_VIN,
            vehicle_name=MOCK_VEHICLE_NAME,
            fuel_type="E",
            car_refresh_unsub=car_unsub,
            location_refresh_unsub=loc_unsub,
        )
        entry = MagicMock()
        entry.runtime_data = SimpleNamespace(
            vehicles={MOCK_VIN: vd},
            api=MagicMock(),
        )
        assert await async_unload_entry(hass, entry) is True
        car_unsub.assert_called_once()
        loc_unsub.assert_called_once()


class TestCleanupRemovedVehicles:
    def test_removes_device_for_missing_vin(self):
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "entry_1"
        device = MagicMock()
        device.identifiers = {("myhondaplus", "OLD_VIN")}
        device.id = "device_old"
        with patch("custom_components.myhondaplus.dr") as mock_dr:
            mock_dr.async_get.return_value = MagicMock()
            mock_dr.async_entries_for_config_entry.return_value = [device]
            _cleanup_removed_vehicles(hass, entry, {"CURRENT_VIN"})
            mock_dr.async_get.return_value.async_remove_device.assert_called_once_with(
                "device_old"
            )

    def test_keeps_device_for_active_vin(self):
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "entry_1"
        device = MagicMock()
        device.identifiers = {("myhondaplus", MOCK_VIN)}
        device.id = "device_1"
        with patch("custom_components.myhondaplus.dr") as mock_dr:
            mock_dr.async_get.return_value = MagicMock()
            mock_dr.async_entries_for_config_entry.return_value = [device]
            _cleanup_removed_vehicles(hass, entry, {MOCK_VIN})
            mock_dr.async_get.return_value.async_remove_device.assert_not_called()


class TestGetCoordinatorEdgeCases:
    def test_device_without_domain_identifier(self):
        from homeassistant.exceptions import ServiceValidationError

        from custom_components.myhondaplus import ATTR_DEVICE, _get_coordinator

        hass = MagicMock()
        device = MagicMock()
        device.identifiers = {("other_domain", "some_id")}
        with patch("custom_components.myhondaplus.dr") as mock_dr:
            mock_dr.async_get.return_value.async_get.return_value = device
            with pytest.raises(ServiceValidationError) as exc_info:
                _get_coordinator(hass, MagicMock(data={ATTR_DEVICE: "dev1"}))
        assert exc_info.value.translation_key == "device_not_found"

    def test_device_with_no_loaded_entry(self, mock_runtime_data):
        from homeassistant.exceptions import ServiceValidationError

        from custom_components.myhondaplus import ATTR_DEVICE, _get_coordinator

        hass = MagicMock()
        device = MagicMock()
        device.identifiers = {("myhondaplus", MOCK_VIN)}
        device.config_entries = {"entry_1"}
        # Entry exists but not loaded
        entry = MagicMock()
        entry.domain = "myhondaplus"
        entry.state = "not_loaded"
        hass.config_entries.async_get_entry.return_value = entry
        with patch("custom_components.myhondaplus.dr") as mock_dr:
            mock_dr.async_get.return_value.async_get.return_value = device
            with pytest.raises(ServiceValidationError) as exc_info:
                _get_coordinator(hass, MagicMock(data={ATTR_DEVICE: "dev1"}))
        assert exc_info.value.translation_key == "device_not_found"


class TestDefrostSwitchSuccess:
    @pytest.mark.asyncio
    async def test_defrost_turn_on_updates_data(self, mock_coordinator):
        mock_coordinator.async_send_command_and_wait.return_value = True
        entity = HondaDefrostSwitch(mock_coordinator, MOCK_VIN, MOCK_VEHICLE_NAME, "E")
        entity.hass = _make_hass_mock()
        await entity.async_turn_on()
        mock_coordinator.async_set_updated_data.assert_called_once()
        updated = mock_coordinator.async_set_updated_data.call_args[0][0]
        assert updated["climate_defrost"] is True


class TestBuildModelNameFromVehicle:
    """Tests for _build_model_name_from_vehicle."""

    def test_friendly_and_grade_and_year(self):
        v = SimpleNamespace(model_name="Honda e", grade="Advance", model_year="2024")
        assert _build_model_name_from_vehicle(v) == "Honda e Advance (2024)"

    def test_friendly_and_grade_with_prefix(self):
        v = SimpleNamespace(model_name="ZR-V", grade="2X Sport", model_year="2025")
        assert _build_model_name_from_vehicle(v) == "ZR-V Sport (2025)"

    def test_only_grade(self):
        v = SimpleNamespace(model_name="", grade="Advance", model_year="")
        assert _build_model_name_from_vehicle(v) == "Advance"

    def test_only_year(self):
        v = SimpleNamespace(model_name="", grade="", model_year="2024")
        assert _build_model_name_from_vehicle(v) == "2024"

    def test_empty(self):
        v = SimpleNamespace(model_name="", grade="", model_year="")
        assert _build_model_name_from_vehicle(v) == ""


class TestFetchVehicleMetadata:
    """Tests for _fetch_vehicle_metadata."""

    @pytest.mark.asyncio
    async def test_returns_vehicles_by_vin(self):
        vehicle = Vehicle(vin=MOCK_VIN, model_name="Honda e")
        api = MagicMock()
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value=[vehicle])
        entry = MagicMock()
        entry.data = {**MOCK_ENTRY_DATA}

        result = await _fetch_vehicle_metadata(hass, entry, api)
        assert MOCK_VIN in result
        assert result[MOCK_VIN].model_name == "Honda e"

    @pytest.mark.asyncio
    async def test_returns_empty_on_exception(self):
        api = MagicMock()
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(side_effect=Exception("fail"))
        entry = MagicMock()
        entry.data = {**MOCK_ENTRY_DATA}

        result = await _fetch_vehicle_metadata(hass, entry, api)
        assert result == {}

    @pytest.mark.asyncio
    async def test_backfills_model_name(self):
        from custom_components.myhondaplus.const import CONF_VEHICLES, CONF_VIN

        vehicle = Vehicle(vin=MOCK_VIN, model_name="Honda e", grade="Advance", model_year="2024")
        api = MagicMock()
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock(return_value=[vehicle])
        entry = MagicMock()
        entry.data = {
            **MOCK_ENTRY_DATA,
            CONF_VEHICLES: [{CONF_VIN: MOCK_VIN}],  # no model
        }

        await _fetch_vehicle_metadata(hass, entry, api)
        hass.config_entries.async_update_entry.assert_called_once()


class TestSensorEnabled:
    """Tests for _sensor_enabled capability/ui_hide filtering."""

    def test_no_capability_always_enabled(self):
        desc = SimpleNamespace(capability="", ui_hide="")
        vehicle = SimpleNamespace(
            capabilities=VehicleCapabilities(),
            ui_config=UIConfiguration(),
        )
        assert _sensor_enabled(desc, vehicle) is True

    def test_capability_false_disables(self):
        desc = SimpleNamespace(capability="remote_charge", ui_hide="")
        vehicle = SimpleNamespace(
            capabilities=VehicleCapabilities(remote_charge=False),
            ui_config=UIConfiguration(),
        )
        assert _sensor_enabled(desc, vehicle) is False

    def test_ui_hide_true_disables(self):
        desc = SimpleNamespace(capability="", ui_hide="hide_internal_temperature")
        vehicle = SimpleNamespace(
            capabilities=VehicleCapabilities(),
            ui_config=UIConfiguration(hide_internal_temperature=True),
        )
        assert _sensor_enabled(desc, vehicle) is False


class TestCommandValueError:
    """Test that ValueError from capability checks is caught."""

    @pytest.mark.asyncio
    async def test_valueerror_raises_ha_error(self):
        coord = HondaDataUpdateCoordinator.__new__(HondaDataUpdateCoordinator)
        coord.hass = MagicMock()
        coord.hass.async_add_executor_job = AsyncMock(
            side_effect=ValueError("not supported")
        )
        with pytest.raises(HomeAssistantError):
            await coord.async_send_command(lambda: None)


class TestConfigFlowDeviceRegistrationError:
    """Test that network errors during device registration are caught."""

    @pytest.mark.asyncio
    async def test_login_device_reset_network_error(self):
        flow = MyHondaPlusConfigFlow()
        flow.hass = MagicMock()
        flow._email = "test@example.com"
        flow._password = "password"
        flow._device_key = MagicMock()
        flow._auth = MagicMock()

        # First call (login) raises device-not-registered
        # Second call (reset) raises a network error
        flow.hass.async_add_executor_job = AsyncMock(
            side_effect=[
                HondaAuthError(403, "device-authenticator-not-registered"),
                Exception("ReadTimeout"),
            ]
        )

        result = await flow.async_step_user({
            "email": "test@example.com",
            "password": "password",
        })
        assert result["errors"]["base"] == "cannot_connect"

    @pytest.mark.asyncio
    async def test_reauth_device_reset_network_error(self):
        flow = MyHondaPlusConfigFlow()
        flow.hass = MagicMock()
        flow._reauth_entry = MagicMock()
        flow._device_key = MagicMock()
        flow._auth = MagicMock()

        flow.hass.async_add_executor_job = AsyncMock(
            side_effect=[
                HondaAuthError(403, "device-authenticator-not-registered"),
                Exception("ReadTimeout"),
            ]
        )

        result = await flow.async_step_reauth_confirm({
            "email": "test@example.com",
            "password": "password",
        })
        assert result["errors"]["base"] == "cannot_connect"
