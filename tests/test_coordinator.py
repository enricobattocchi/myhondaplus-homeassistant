"""Tests for the coordinator."""

from collections import namedtuple
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed
from pymyhondaplus.api import HondaAPIError, HondaAuthError

from custom_components.myhondaplus.coordinator import (
    HondaDataUpdateCoordinator,
    HondaTripCoordinator,
)

from .conftest import MOCK_DASHBOARD_DATA, MOCK_ENTRY_DATA, MOCK_VEHICLE_NAME, MOCK_VIN

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
    with patch.object(
        HondaDataUpdateCoordinator, "__init__", lambda self, *a, **kw: None
    ):
        coord = HondaDataUpdateCoordinator.__new__(HondaDataUpdateCoordinator)
        coord.hass = mock_hass
        coord.entry = mock_entry
        coord.vin = MOCK_VIN
        coord.api = MagicMock()
        coord.api.tokens = Tokens("fake-access-token", "fake-refresh-token")
        coord.data = dict(MOCK_DASHBOARD_DATA)
        coord.logger = MagicMock()
        coord._service_available = True
        coord._vehicle_name = MOCK_VEHICLE_NAME
        coord.async_set_updated_data = MagicMock()
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
        coord._service_available = True
        return coord


class TestHondaDataUpdateCoordinator:
    @pytest.mark.asyncio
    async def test_update_success(self, coordinator):
        coordinator.hass.async_add_executor_job.return_value = dict(MOCK_DASHBOARD_DATA)
        result = await coordinator._async_update_data()
        assert result["battery_level"] == 75

    @pytest.mark.asyncio
    async def test_update_401_raises_auth_failed(self, coordinator):
        coordinator.hass.async_add_executor_job.side_effect = HondaAuthError(
            401, "Unauthorized"
        )
        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_update_502_returns_cached_data(self, coordinator):
        coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(
            502, "Bad Gateway"
        )
        result = await coordinator._async_update_data()
        assert result == coordinator.data

    @pytest.mark.asyncio
    async def test_update_500_returns_cached_data(self, coordinator):
        coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(
            500, "Internal Server Error"
        )
        result = await coordinator._async_update_data()
        assert result == coordinator.data

    @pytest.mark.asyncio
    async def test_update_503_returns_cached_data(self, coordinator):
        coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(
            503, "Service Unavailable"
        )
        result = await coordinator._async_update_data()
        assert result == coordinator.data

    @pytest.mark.asyncio
    async def test_update_500_no_cached_data_raises(self, coordinator):
        coordinator.data = None
        coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(
            500, "Internal Server Error"
        )
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_update_400_raises_update_failed(self, coordinator):
        coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(
            400, "Bad Request"
        )
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_update_generic_exception_raises(self, coordinator):
        coordinator.hass.async_add_executor_job.side_effect = RuntimeError("boom")
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_update_logs_unavailable_once_and_recovered_once(self, coordinator):
        with patch("custom_components.myhondaplus.coordinator.LOGGER") as logger:
            coordinator.hass.async_add_executor_job.side_effect = [
                HondaAPIError(503, "Service Unavailable"),
                HondaAPIError(503, "Service Unavailable"),
                dict(MOCK_DASHBOARD_DATA),
            ]

            assert await coordinator._async_update_data() == coordinator.data
            assert await coordinator._async_update_data() == coordinator.data
            await coordinator._async_update_data()

        logger.warning.assert_called_once_with(
            "Honda API unavailable (%s), keeping cached vehicle data",
            503,
        )
        logger.info.assert_called_once_with("Connection to Honda API restored")

    @pytest.mark.asyncio
    async def test_refresh_from_car_success(self, coordinator):
        coordinator.hass.async_add_executor_job.side_effect = [
            SimpleNamespace(
                success=True, status="success", timed_out=False, reason=None
            ),
            dict(MOCK_DASHBOARD_DATA),
        ]
        await coordinator.async_refresh_from_car()
        coordinator.async_set_updated_data.assert_called_once()
        assert coordinator.hass.async_add_executor_job.await_args_list[0].args == (
            coordinator._refresh_from_car,
        )
        assert coordinator.hass.async_add_executor_job.await_args_list[1].args == (
            coordinator._fetch_data,
        )

    @pytest.mark.asyncio
    async def test_refresh_from_car_401(self, coordinator):
        coordinator.hass.async_add_executor_job.side_effect = HondaAuthError(
            401, "Unauthorized"
        )
        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator.async_refresh_from_car()

    @pytest.mark.asyncio
    async def test_refresh_from_car_502(self, coordinator):
        coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(
            502, "Bad Gateway"
        )
        with pytest.raises(HomeAssistantError) as exc_info:
            await coordinator.async_refresh_from_car()
        assert exc_info.value.translation_key == "refresh_data_failed"

    @pytest.mark.asyncio
    async def test_refresh_from_car_timeout_raises(self, coordinator):
        coordinator.hass.async_add_executor_job.return_value = SimpleNamespace(
            success=False,
            status="pending",
            timed_out=True,
            reason=None,
        )

        with patch("custom_components.myhondaplus.coordinator.LOGGER") as logger:
            with patch(
                "custom_components.myhondaplus.coordinator.pn_async_create"
            ) as pn_create:
                with pytest.raises(HomeAssistantError) as exc_info:
                    await coordinator.async_refresh_from_car()
                assert exc_info.value.translation_key == "refresh_data_failed"

        coordinator.async_set_updated_data.assert_not_called()
        logger.warning.assert_called_once_with(
            "Dashboard refresh timed out waiting for the car to respond (status=%s, reason=%s)",
            "pending",
            None,
        )
        pn_create.assert_called_once_with(
            coordinator.hass,
            f"Dashboard refresh for {MOCK_VEHICLE_NAME} timed out waiting for the car to respond.",
            title="My Honda+",
            notification_id="myhondaplus_refresh_timeout",
        )

    @pytest.mark.asyncio
    async def test_refresh_from_car_failure_no_notification(self, coordinator):
        coordinator.hass.async_add_executor_job.return_value = SimpleNamespace(
            success=False,
            status="failed",
            timed_out=False,
            reason="error",
        )

        with patch(
            "custom_components.myhondaplus.coordinator.pn_async_create"
        ) as pn_create:
            with pytest.raises(HomeAssistantError) as exc_info:
                await coordinator.async_refresh_from_car()
            assert exc_info.value.translation_key == "refresh_data_failed"

        pn_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_command_success(self, coordinator):
        func = MagicMock()
        coordinator.hass.async_add_executor_job.return_value = "ok"
        result = await coordinator.async_send_command(func, "arg1", "arg2")
        assert result == "ok"
        coordinator.hass.async_add_executor_job.assert_awaited_once_with(
            func, "arg1", "arg2"
        )

    @pytest.mark.asyncio
    async def test_send_command_401(self, coordinator):
        func = MagicMock()
        coordinator.hass.async_add_executor_job.side_effect = HondaAuthError(
            401, "Unauthorized"
        )
        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator.async_send_command(func)

    @pytest.mark.asyncio
    async def test_send_command_500(self, coordinator):
        func = MagicMock()
        coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(
            500, "Error"
        )
        with pytest.raises(HomeAssistantError) as exc_info:
            await coordinator.async_send_command(func)
        assert exc_info.value.translation_key == "send_command_failed"

    @pytest.mark.asyncio
    async def test_send_command_and_wait_uses_90_second_timeout(self, coordinator):
        func = MagicMock()
        coordinator.async_send_command = AsyncMock(return_value="cmd-123")
        coordinator.hass.async_add_executor_job.return_value = SimpleNamespace(
            success=True,
            status="success",
            timed_out=False,
            reason=None,
        )

        assert await coordinator.async_send_command_and_wait(func, "arg1") is True

        coordinator.hass.async_add_executor_job.assert_awaited_once_with(
            coordinator.api.wait_for_command,
            "cmd-123",
            90,
        )

    @pytest.mark.asyncio
    async def test_send_command_and_wait_timeout_logs_and_notifies(self, coordinator):
        func = MagicMock()
        coordinator.async_send_command = AsyncMock(return_value="cmd-123")
        coordinator.hass.async_add_executor_job.return_value = SimpleNamespace(
            success=False,
            status="timeout",
            timed_out=True,
            reason=None,
        )

        with patch("custom_components.myhondaplus.coordinator.LOGGER") as logger:
            with patch(
                "custom_components.myhondaplus.coordinator.pn_async_create"
            ) as pn_create:
                assert (
                    await coordinator.async_send_command_and_wait(func, "arg1") is False
                )

        logger.warning.assert_called_once_with(
            "Command timed out waiting for the car to respond (id=%s, status=%s, reason=%s)",
            "cmd-123",
            "timeout",
            None,
        )
        pn_create.assert_called_once_with(
            coordinator.hass,
            f"A command for {MOCK_VEHICLE_NAME} timed out waiting for the car to respond.",
            title="My Honda+",
            notification_id="myhondaplus_command_timeout",
        )

    @pytest.mark.asyncio
    async def test_send_command_and_wait_failure_no_notification(self, coordinator):
        func = MagicMock()
        coordinator.async_send_command = AsyncMock(return_value="cmd-123")
        coordinator.hass.async_add_executor_job.return_value = SimpleNamespace(
            success=False,
            status="failed",
            timed_out=False,
            reason="error",
        )

        with patch(
            "custom_components.myhondaplus.coordinator.pn_async_create"
        ) as pn_create:
            assert await coordinator.async_send_command_and_wait(func, "arg1") is False

        pn_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_location_success(self, coordinator):
        coordinator.async_send_command = AsyncMock(return_value="cmd-123")
        coordinator.hass.async_add_executor_job.side_effect = [
            SimpleNamespace(
                success=True, status="success", timed_out=False, reason=None
            ),
            dict(MOCK_DASHBOARD_DATA),
        ]

        await coordinator.async_refresh_location()

        coordinator.async_send_command.assert_awaited_once_with(
            coordinator.api.request_car_location,
            MOCK_VIN,
        )
        assert coordinator.hass.async_add_executor_job.await_args_list[0].args == (
            coordinator.api.wait_for_command,
            "cmd-123",
            90,
        )
        assert coordinator.hass.async_add_executor_job.await_args_list[1].args == (
            coordinator._fetch_data,
        )
        coordinator.async_set_updated_data.assert_called_once_with(
            dict(MOCK_DASHBOARD_DATA)
        )

    @pytest.mark.asyncio
    async def test_refresh_location_command_failure_raises(self, coordinator):
        coordinator.async_send_command = AsyncMock(return_value="cmd-123")
        coordinator.hass.async_add_executor_job.return_value = SimpleNamespace(
            success=False,
            status="timeout",
            timed_out=True,
            reason=None,
        )

        with patch("custom_components.myhondaplus.coordinator.LOGGER") as logger:
            with patch(
                "custom_components.myhondaplus.coordinator.pn_async_create"
            ) as pn_create:
                with pytest.raises(HomeAssistantError) as exc_info:
                    await coordinator.async_refresh_location()
                assert exc_info.value.translation_key == "refresh_location_failed"

        coordinator.async_set_updated_data.assert_not_called()
        coordinator.hass.async_add_executor_job.assert_awaited_once_with(
            coordinator.api.wait_for_command,
            "cmd-123",
            90,
        )
        logger.warning.assert_called_once_with(
            "Location refresh timed out waiting for the car to respond (id=%s, status=%s, reason=%s)",
            "cmd-123",
            "timeout",
            None,
        )
        pn_create.assert_called_once_with(
            coordinator.hass,
            f"Location refresh for {MOCK_VEHICLE_NAME} timed out waiting for the car to respond.",
            title="My Honda+",
            notification_id="myhondaplus_location_timeout",
        )

    @pytest.mark.asyncio
    async def test_refresh_location_timeout_without_notification(self, coordinator):
        coordinator.async_send_command = AsyncMock(return_value="cmd-123")
        coordinator.hass.async_add_executor_job.return_value = SimpleNamespace(
            success=False,
            status="timeout",
            timed_out=True,
            reason=None,
        )

        with patch(
            "custom_components.myhondaplus.coordinator.pn_async_create"
        ) as pn_create:
            with pytest.raises(HomeAssistantError) as exc_info:
                await coordinator.async_refresh_location(notify_on_timeout=False)
            assert exc_info.value.translation_key == "refresh_location_failed"

        pn_create.assert_not_called()


class TestHondaTripCoordinator:
    @pytest.mark.asyncio
    async def test_update_success(self, trip_coordinator):
        trip_coordinator.hass.async_add_executor_job.return_value = {"trips": 5}
        result = await trip_coordinator._async_update_data()
        assert result == {"trips": 5}

    @pytest.mark.asyncio
    async def test_update_401_raises_auth_failed(self, trip_coordinator):
        trip_coordinator.hass.async_add_executor_job.side_effect = HondaAuthError(
            401, "Unauthorized"
        )
        with pytest.raises(ConfigEntryAuthFailed):
            await trip_coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_update_502_returns_cached_data(self, trip_coordinator):
        trip_coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(
            502, "Bad Gateway"
        )
        result = await trip_coordinator._async_update_data()
        assert result == trip_coordinator.data

    @pytest.mark.asyncio
    async def test_update_500_no_cached_data_raises(self, trip_coordinator):
        trip_coordinator.data = None
        trip_coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(
            500, "Error"
        )
        with pytest.raises(UpdateFailed):
            await trip_coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_update_400_raises_update_failed(self, trip_coordinator):
        trip_coordinator.hass.async_add_executor_job.side_effect = HondaAPIError(
            400, "Bad Request"
        )
        with pytest.raises(UpdateFailed):
            await trip_coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_update_logs_unavailable_once_and_recovered_once(
        self, trip_coordinator
    ):
        with patch("custom_components.myhondaplus.coordinator.LOGGER") as logger:
            trip_coordinator.hass.async_add_executor_job.side_effect = [
                HondaAPIError(502, "Bad Gateway"),
                HondaAPIError(502, "Bad Gateway"),
                {"trips": 5},
            ]

            assert await trip_coordinator._async_update_data() == trip_coordinator.data
            assert await trip_coordinator._async_update_data() == trip_coordinator.data
            await trip_coordinator._async_update_data()

        logger.warning.assert_called_once_with(
            "Honda API unavailable (%s), keeping cached trip data",
            502,
        )
        logger.info.assert_called_once_with("Connection to Honda API restored")
