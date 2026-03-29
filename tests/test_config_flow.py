"""Tests for the config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymyhondaplus.api import HondaAuthError

from custom_components.myhondaplus.config_flow import (
    MyHondaPlusConfigFlow,
    MyHondaPlusOptionsFlow,
)
from custom_components.myhondaplus.const import (
    CONF_CAR_REFRESH_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_VEHICLE_NAME,
    CONF_VIN,
    DEFAULT_CAR_REFRESH_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
)

from .conftest import MOCK_VEHICLE_NAME, MOCK_VIN

MOCK_TOKENS = {"access_token": "fake-access", "refresh_token": "fake-refresh"}
MOCK_VEHICLES = [
    {"vin": MOCK_VIN, "name": MOCK_VEHICLE_NAME, "plate": "AB123CD", "fuel_type": "E"},
]
MOCK_VEHICLES_MULTI = [
    {"vin": MOCK_VIN, "name": MOCK_VEHICLE_NAME, "plate": "AB123CD", "fuel_type": "E"},
    {"vin": "ZHWGE11S00LA00002", "name": "Honda e:Ny1", "plate": "EF456GH", "fuel_type": "E"},
]
MOCK_USER_INFO = {"personalId": "12345"}


@pytest.fixture
def flow():
    """Create a config flow instance with mocked hass."""
    f = MyHondaPlusConfigFlow()
    f.hass = MagicMock()
    f.hass.async_add_executor_job = AsyncMock()
    f.hass.config_entries = MagicMock()
    # Mock HA flow methods
    f.async_set_unique_id = AsyncMock()
    f._abort_if_unique_id_configured = MagicMock()
    f.async_show_form = MagicMock(return_value={"type": "form"})
    f.async_create_entry = MagicMock(return_value={"type": "create_entry"})
    return f


class TestAsyncStepUser:
    @pytest.mark.asyncio
    async def test_shows_form_on_first_call(self, flow):
        await flow.async_step_user(None)
        flow.async_show_form.assert_called_once()
        assert flow.async_show_form.call_args[1]["step_id"] == "user"

    @pytest.mark.asyncio
    async def test_happy_path_single_vehicle(self, flow):
        """Login succeeds, one vehicle found → creates entry."""
        flow.hass.async_add_executor_job.side_effect = [
            MOCK_TOKENS,  # login
            MOCK_VEHICLES,  # get_vehicles
            MOCK_USER_INFO,  # get_user_info
        ]

        with patch("custom_components.myhondaplus.config_flow.DeviceKey"), \
             patch("custom_components.myhondaplus.config_flow.HondaAuth") as mock_auth_cls, \
             patch("custom_components.myhondaplus.config_flow.HondaAPI") as mock_api_cls:
            mock_auth = MagicMock()
            mock_auth_cls.return_value = mock_auth
            mock_auth_cls.extract_user_id.return_value = "fake-user-id"
            mock_api = MagicMock()
            mock_api_cls.return_value = mock_api

            await flow.async_step_user({
                "email": "test@test.com",
                "password": "pass123",
                "scan_interval": 600,
                "car_refresh_interval": 43200,
            })

        flow.async_create_entry.assert_called_once()
        entry_data = flow.async_create_entry.call_args[1]["data"]
        assert entry_data[CONF_VIN] == MOCK_VIN
        assert entry_data[CONF_VEHICLE_NAME] == MOCK_VEHICLE_NAME
        assert entry_data[CONF_SCAN_INTERVAL] == 600

    @pytest.mark.asyncio
    async def test_invalid_credentials(self, flow):
        """Login with bad credentials shows error."""
        with patch("custom_components.myhondaplus.config_flow.DeviceKey"), \
             patch("custom_components.myhondaplus.config_flow.HondaAuth"):
            flow.hass.async_add_executor_job.side_effect = HondaAuthError(401, "invalid-credentials")
            await flow.async_step_user({
                "email": "test@test.com",
                "password": "wrong",
                "scan_interval": 600,
                "car_refresh_interval": 43200,
            })

        flow.async_show_form.assert_called()
        errors = flow.async_show_form.call_args[1]["errors"]
        assert errors["base"] == "invalid_auth"

    @pytest.mark.asyncio
    async def test_locked_account(self, flow):
        """Locked account shows error."""
        with patch("custom_components.myhondaplus.config_flow.DeviceKey"), \
             patch("custom_components.myhondaplus.config_flow.HondaAuth"):
            flow.hass.async_add_executor_job.side_effect = HondaAuthError(401, "locked-account")
            await flow.async_step_user({
                "email": "test@test.com",
                "password": "pass",
                "scan_interval": 600,
                "car_refresh_interval": 43200,
            })

        errors = flow.async_show_form.call_args[1]["errors"]
        assert errors["base"] == "account_locked"

    @pytest.mark.asyncio
    async def test_device_not_registered_goes_to_verify(self, flow):
        """Device-authenticator-not-registered triggers verification flow."""
        with patch("custom_components.myhondaplus.config_flow.DeviceKey"), \
             patch("custom_components.myhondaplus.config_flow.HondaAuth") as mock_auth_cls:
            mock_auth = MagicMock()
            mock_auth_cls.return_value = mock_auth

            # First call: login fails with device-authenticator-not-registered
            # Second call: reset_device_authenticator succeeds
            flow.hass.async_add_executor_job.side_effect = [
                HondaAuthError(401, "device-authenticator-not-registered"),
                None,  # reset_device_authenticator
            ]
            await flow.async_step_user({
                "email": "test@test.com",
                "password": "pass",
                "scan_interval": 600,
                "car_refresh_interval": 43200,
            })

        # Should show the verify form
        flow.async_show_form.assert_called()
        assert flow.async_show_form.call_args[1]["step_id"] == "verify"

    @pytest.mark.asyncio
    async def test_generic_exception(self, flow):
        """Unexpected exception shows cannot_connect."""
        with patch("custom_components.myhondaplus.config_flow.DeviceKey"), \
             patch("custom_components.myhondaplus.config_flow.HondaAuth"):
            flow.hass.async_add_executor_job.side_effect = Exception("unexpected")
            await flow.async_step_user({
                "email": "test@test.com",
                "password": "pass",
                "scan_interval": 600,
                "car_refresh_interval": 43200,
            })

        errors = flow.async_show_form.call_args[1]["errors"]
        assert errors["base"] == "cannot_connect"


class TestAsyncStepVerify:
    @pytest.mark.asyncio
    async def test_shows_form_on_first_call(self, flow):
        await flow.async_step_verify(None)
        flow.async_show_form.assert_called_once()
        assert flow.async_show_form.call_args[1]["step_id"] == "verify"

    @pytest.mark.asyncio
    async def test_invalid_link(self, flow):
        """Invalid verification link shows error."""
        with patch("custom_components.myhondaplus.config_flow.HondaAuth") as mock_auth_cls:
            mock_auth_cls.parse_verify_link_key.return_value = (None, None)
            await flow.async_step_verify({"verification_link": "bad-link"})

        errors = flow.async_show_form.call_args[1]["errors"]
        assert errors["base"] == "invalid_link"

    @pytest.mark.asyncio
    async def test_valid_link_success(self, flow):
        """Valid link → verify → login → create entry."""
        flow._email = "test@test.com"
        flow._password = "pass"
        flow._device_key = MagicMock()
        flow._device_key.pem_bytes = b"fake-pem"
        flow._auth = MagicMock()
        flow._scan_interval = DEFAULT_SCAN_INTERVAL
        flow._car_refresh_interval = DEFAULT_CAR_REFRESH_INTERVAL

        with patch("custom_components.myhondaplus.config_flow.HondaAuth") as mock_auth_cls, \
             patch("custom_components.myhondaplus.config_flow.HondaAPI") as mock_api_cls:
            mock_auth_cls.parse_verify_link_key.return_value = ("key123", "link_type")
            mock_auth_cls.extract_user_id.return_value = "fake-user-id"
            mock_api = MagicMock()
            mock_api_cls.return_value = mock_api

            flow.hass.async_add_executor_job.side_effect = [
                None,  # verify_magic_link
                MOCK_TOKENS,  # login
                MOCK_VEHICLES,  # get_vehicles
                MOCK_USER_INFO,  # get_user_info
            ]

            await flow.async_step_verify({"verification_link": "https://honda.com/verify?key=abc"})

        flow.async_create_entry.assert_called_once()


class TestAsyncStepSelectVehicle:
    @pytest.mark.asyncio
    async def test_multiple_vehicles_shows_selection(self, flow):
        """Multiple vehicles shows selection form."""
        flow._vehicles = MOCK_VEHICLES_MULTI
        await flow.async_step_select_vehicle(None)
        flow.async_show_form.assert_called_once()
        assert flow.async_show_form.call_args[1]["step_id"] == "select_vehicle"

    @pytest.mark.asyncio
    async def test_select_vehicle_creates_entry(self, flow):
        """Selecting a vehicle creates an entry."""
        flow._vehicles = MOCK_VEHICLES_MULTI
        flow._tokens = MOCK_TOKENS
        flow._email = "test@test.com"
        flow._scan_interval = DEFAULT_SCAN_INTERVAL
        flow._car_refresh_interval = DEFAULT_CAR_REFRESH_INTERVAL
        flow._device_key = MagicMock()
        flow._device_key.pem_bytes = b"fake-pem"
        flow._api = None

        with patch("custom_components.myhondaplus.config_flow.HondaAuth") as mock_auth_cls, \
             patch("custom_components.myhondaplus.config_flow.HondaAPI") as mock_api_cls:
            mock_auth_cls.extract_user_id.return_value = "fake-user-id"
            mock_api = MagicMock()
            mock_api_cls.return_value = mock_api
            flow.hass.async_add_executor_job.side_effect = [MOCK_USER_INFO]

            await flow.async_step_select_vehicle({CONF_VIN: MOCK_VIN})

        flow.async_create_entry.assert_called_once()
        entry_data = flow.async_create_entry.call_args[1]["data"]
        assert entry_data[CONF_VIN] == MOCK_VIN


class TestAsyncStepManualVin:
    @pytest.mark.asyncio
    async def test_shows_form_on_first_call(self, flow):
        await flow.async_step_manual_vin(None)
        flow.async_show_form.assert_called_once()
        assert flow.async_show_form.call_args[1]["step_id"] == "manual_vin"

    @pytest.mark.asyncio
    async def test_manual_vin_creates_entry(self, flow):
        """Manual VIN entry creates an entry."""
        flow._tokens = MOCK_TOKENS
        flow._email = "test@test.com"
        flow._scan_interval = DEFAULT_SCAN_INTERVAL
        flow._car_refresh_interval = DEFAULT_CAR_REFRESH_INTERVAL
        flow._device_key = MagicMock()
        flow._device_key.pem_bytes = b"fake-pem"
        flow._api = None

        with patch("custom_components.myhondaplus.config_flow.HondaAuth") as mock_auth_cls, \
             patch("custom_components.myhondaplus.config_flow.HondaAPI") as mock_api_cls:
            mock_auth_cls.extract_user_id.return_value = "fake-user-id"
            mock_api = MagicMock()
            mock_api_cls.return_value = mock_api
            flow.hass.async_add_executor_job.side_effect = [MOCK_USER_INFO]

            await flow.async_step_manual_vin({CONF_VIN: "MANUAL12345678901"})

        flow.async_create_entry.assert_called_once()
        entry_data = flow.async_create_entry.call_args[1]["data"]
        assert entry_data[CONF_VIN] == "MANUAL12345678901"
        assert entry_data[CONF_VEHICLE_NAME] == ""


class TestOptionsFlow:
    @pytest.mark.asyncio
    async def test_shows_form_on_first_call(self):
        mock_entry = MagicMock()
        mock_entry.data = {
            CONF_SCAN_INTERVAL: 600,
            CONF_CAR_REFRESH_INTERVAL: 43200,
        }
        flow = MyHondaPlusOptionsFlow()
        flow.hass = MagicMock()
        flow.async_show_form = MagicMock(return_value={"type": "form"})

        with patch.object(type(flow), "config_entry", new_callable=lambda: property(lambda self: mock_entry)):
            await flow.async_step_init(None)

        flow.async_show_form.assert_called_once()
        assert flow.async_show_form.call_args[1]["step_id"] == "init"

    @pytest.mark.asyncio
    async def test_updates_entry_and_reloads(self):
        mock_entry = MagicMock()
        mock_entry.data = {
            CONF_SCAN_INTERVAL: 600,
            CONF_CAR_REFRESH_INTERVAL: 43200,
        }
        flow = MyHondaPlusOptionsFlow()
        flow.hass = MagicMock()
        flow.hass.config_entries.async_reload = AsyncMock()
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})

        with patch.object(type(flow), "config_entry", new_callable=lambda: property(lambda self: mock_entry)):
            await flow.async_step_init({
                CONF_SCAN_INTERVAL: 300,
                CONF_CAR_REFRESH_INTERVAL: 7200,
            })

        flow.hass.config_entries.async_update_entry.assert_called_once()
        flow.hass.config_entries.async_reload.assert_awaited_once()
        flow.async_create_entry.assert_called_once()


class TestReauthFlow:
    @pytest.fixture
    def reauth_flow(self):
        """Create a config flow primed for reauth."""
        f = MyHondaPlusConfigFlow()
        f.hass = MagicMock()
        f.hass.async_add_executor_job = AsyncMock()
        f.hass.config_entries = MagicMock()
        f.hass.config_entries.async_get_entry.return_value = MagicMock()
        f.async_set_unique_id = AsyncMock()
        f._abort_if_unique_id_configured = MagicMock()
        f.async_show_form = MagicMock(return_value={"type": "form"})
        f.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        f.async_abort = MagicMock(return_value={"type": "abort"})
        return f

    @pytest.mark.asyncio
    async def test_reauth_shows_confirm_form(self, reauth_flow):
        """Reauth step shows the confirm form."""
        reauth_flow.context = {"entry_id": "test_entry"}
        await reauth_flow.async_step_reauth({})
        reauth_flow.async_show_form.assert_called()
        assert reauth_flow.async_show_form.call_args[1]["step_id"] == "reauth_confirm"

    @pytest.mark.asyncio
    async def test_reauth_success(self, reauth_flow):
        """Successful reauth updates entry and aborts with reauth_successful."""
        reauth_flow.context = {"entry_id": "test_entry"}
        await reauth_flow.async_step_reauth({})

        with patch("custom_components.myhondaplus.config_flow.DeviceKey"), \
             patch("custom_components.myhondaplus.config_flow.HondaAuth") as mock_auth_cls, \
             patch("custom_components.myhondaplus.config_flow.HondaAPI"):
            mock_auth = MagicMock()
            mock_auth_cls.return_value = mock_auth
            mock_auth_cls.extract_user_id.return_value = "fake-user-id"
            reauth_flow.hass.async_add_executor_job.side_effect = [MOCK_TOKENS]

            await reauth_flow.async_step_reauth_confirm({
                "email": "test@test.com",
                "password": "newpass",
            })

        reauth_flow.hass.config_entries.async_update_entry.assert_called_once()
        reauth_flow.async_abort.assert_called_once_with(reason="reauth_successful")

    @pytest.mark.asyncio
    async def test_reauth_invalid_credentials(self, reauth_flow):
        """Bad credentials during reauth show error."""
        reauth_flow.context = {"entry_id": "test_entry"}
        await reauth_flow.async_step_reauth({})

        with patch("custom_components.myhondaplus.config_flow.DeviceKey"), \
             patch("custom_components.myhondaplus.config_flow.HondaAuth"):
            reauth_flow.hass.async_add_executor_job.side_effect = HondaAuthError(401, "invalid-credentials")
            await reauth_flow.async_step_reauth_confirm({
                "email": "test@test.com",
                "password": "wrong",
            })

        errors = reauth_flow.async_show_form.call_args[1]["errors"]
        assert errors["base"] == "invalid_auth"
