"""Tests for the config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymyhondaplus.api import HondaAuthError

from custom_components.myhondaplus.config_flow import (
    MyHondaPlusConfigFlow,
    MyHondaPlusOptionsFlow,
    _reconcile_vehicles,
)
from custom_components.myhondaplus.const import (
    CONF_CAR_REFRESH_INTERVAL,
    CONF_FUEL_TYPE,
    CONF_LOCATION_REFRESH_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_VEHICLE_NAME,
    CONF_VEHICLES,
    CONF_VIN,
    DEFAULT_CAR_REFRESH_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
)

from .conftest import MOCK_VEHICLE_NAME, MOCK_VIN

MOCK_TOKENS = {"access_token": "fake-access", "refresh_token": "fake-refresh"}
MOCK_USER_INFO = {
    "personalId": "12345",
    "vehiclesInfo": [
        {
            "vin": MOCK_VIN,
            "vehicleNickName": MOCK_VEHICLE_NAME,
            "vehicleRegNumber": "AB123CD",
            "fuelType": "E",
            "vehicleUIConfiguration": {"friendlyModelName": "Honda e"},
            "grade": "E ADVANCE",
            "modelYear": 2020,
        },
    ],
}
MOCK_USER_INFO_MULTI = {
    "personalId": "12345",
    "vehiclesInfo": [
        {
            "vin": MOCK_VIN,
            "vehicleNickName": MOCK_VEHICLE_NAME,
            "vehicleRegNumber": "AB123CD",
            "fuelType": "E",
            "vehicleUIConfiguration": {"friendlyModelName": "Honda e"},
            "grade": "E ADVANCE",
            "modelYear": 2020,
        },
        {
            "vin": "ZHWGE11S00LA00002",
            "vehicleNickName": "Honda e:Ny1",
            "vehicleRegNumber": "EF456GH",
            "fuelType": "E",
            "vehicleUIConfiguration": {"friendlyModelName": "Honda e:Ny1"},
            "grade": "E ADVANCE",
            "modelYear": 2024,
        },
    ],
}


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
        """Login succeeds, one vehicle found → creates entry with vehicles list."""
        flow.hass.async_add_executor_job.side_effect = [
            MOCK_TOKENS,  # login
            MOCK_USER_INFO,  # get_user_info (vehicles + personalId)
        ]

        with (
            patch("custom_components.myhondaplus.config_flow.DeviceKey"),
            patch(
                "custom_components.myhondaplus.config_flow.HondaAuth"
            ) as mock_auth_cls,
            patch("custom_components.myhondaplus.config_flow.HondaAPI") as mock_api_cls,
        ):
            mock_auth = MagicMock()
            mock_auth_cls.return_value = mock_auth
            mock_auth_cls.extract_user_id.return_value = "fake-user-id"
            mock_api = MagicMock()
            mock_api_cls.return_value = mock_api

            await flow.async_step_user(
                {
                    "email": "test@test.com",
                    "password": "pass123",
                    "scan_interval": 600,
                    "car_refresh_interval": 43200,
                    "location_refresh_interval": 1800,
                }
            )

        flow.async_create_entry.assert_called_once()
        entry_kwargs = flow.async_create_entry.call_args[1]
        entry_data = entry_kwargs["data"]
        entry_options = entry_kwargs["options"]
        # Vehicles stored as list
        vehicles = entry_data[CONF_VEHICLES]
        assert len(vehicles) == 1
        assert vehicles[0][CONF_VIN] == MOCK_VIN
        assert vehicles[0][CONF_VEHICLE_NAME] == MOCK_VEHICLE_NAME
        # No top-level VIN
        assert CONF_VIN not in entry_data
        assert CONF_SCAN_INTERVAL not in entry_data
        assert entry_options[CONF_SCAN_INTERVAL] == 600
        assert entry_options[CONF_LOCATION_REFRESH_INTERVAL] == 1800
        # Title is email-based
        assert "test@test.com" in entry_kwargs["title"]

    @pytest.mark.asyncio
    async def test_happy_path_multi_vehicle(self, flow):
        """Login succeeds, multiple vehicles → creates entry with all vehicles."""
        flow.hass.async_add_executor_job.side_effect = [
            MOCK_TOKENS,  # login
            MOCK_USER_INFO_MULTI,  # get_user_info
        ]

        with (
            patch("custom_components.myhondaplus.config_flow.DeviceKey"),
            patch(
                "custom_components.myhondaplus.config_flow.HondaAuth"
            ) as mock_auth_cls,
            patch("custom_components.myhondaplus.config_flow.HondaAPI") as mock_api_cls,
        ):
            mock_auth_cls.return_value = MagicMock()
            mock_auth_cls.extract_user_id.return_value = "fake-user-id"
            mock_api_cls.return_value = MagicMock()

            await flow.async_step_user(
                {
                    "email": "test@test.com",
                    "password": "pass123",
                    "scan_interval": 600,
                    "car_refresh_interval": 43200,
                    "location_refresh_interval": 1800,
                }
            )

        flow.async_create_entry.assert_called_once()
        vehicles = flow.async_create_entry.call_args[1]["data"][CONF_VEHICLES]
        assert len(vehicles) == 2
        vins = {v[CONF_VIN] for v in vehicles}
        assert vins == {MOCK_VIN, "ZHWGE11S00LA00002"}

    @pytest.mark.asyncio
    async def test_invalid_credentials(self, flow):
        """Login with bad credentials shows error."""
        with (
            patch("custom_components.myhondaplus.config_flow.DeviceKey"),
            patch("custom_components.myhondaplus.config_flow.HondaAuth"),
        ):
            flow.hass.async_add_executor_job.side_effect = HondaAuthError(
                401, "invalid-credentials"
            )
            await flow.async_step_user(
                {
                    "email": "test@test.com",
                    "password": "wrong",
                    "scan_interval": 600,
                    "car_refresh_interval": 43200,
                }
            )

        flow.async_show_form.assert_called()
        errors = flow.async_show_form.call_args[1]["errors"]
        assert errors["base"] == "invalid_auth"

    @pytest.mark.asyncio
    async def test_locked_account(self, flow):
        """Locked account shows error."""
        with (
            patch("custom_components.myhondaplus.config_flow.DeviceKey"),
            patch("custom_components.myhondaplus.config_flow.HondaAuth"),
        ):
            flow.hass.async_add_executor_job.side_effect = HondaAuthError(
                401, "locked-account"
            )
            await flow.async_step_user(
                {
                    "email": "test@test.com",
                    "password": "pass",
                    "scan_interval": 600,
                    "car_refresh_interval": 43200,
                }
            )

        errors = flow.async_show_form.call_args[1]["errors"]
        assert errors["base"] == "account_locked"

    @pytest.mark.asyncio
    async def test_device_not_registered_goes_to_verify(self, flow):
        """Device-authenticator-not-registered triggers verification flow."""
        with (
            patch("custom_components.myhondaplus.config_flow.DeviceKey"),
            patch(
                "custom_components.myhondaplus.config_flow.HondaAuth"
            ) as mock_auth_cls,
        ):
            mock_auth = MagicMock()
            mock_auth_cls.return_value = mock_auth

            flow.hass.async_add_executor_job.side_effect = [
                HondaAuthError(401, "device-authenticator-not-registered"),
                None,  # reset_device_authenticator
            ]
            await flow.async_step_user(
                {
                    "email": "test@test.com",
                    "password": "pass",
                    "scan_interval": 600,
                    "car_refresh_interval": 43200,
                }
            )

        flow.async_show_form.assert_called()
        assert flow.async_show_form.call_args[1]["step_id"] == "verify"

    @pytest.mark.asyncio
    async def test_device_reset_failure_shows_cannot_connect(self, flow):
        with (
            patch("custom_components.myhondaplus.config_flow.DeviceKey"),
            patch(
                "custom_components.myhondaplus.config_flow.HondaAuth"
            ) as mock_auth_cls,
        ):
            mock_auth = MagicMock()
            mock_auth_cls.return_value = mock_auth

            flow.hass.async_add_executor_job.side_effect = [
                HondaAuthError(401, "device-authenticator-not-registered"),
                HondaAuthError(401, "reset failed"),
            ]
            await flow.async_step_user(
                {
                    "email": "test@test.com",
                    "password": "pass",
                    "scan_interval": 600,
                    "car_refresh_interval": 43200,
                }
            )

        errors = flow.async_show_form.call_args[1]["errors"]
        assert errors["base"] == "cannot_connect"

    @pytest.mark.asyncio
    async def test_unknown_honda_auth_error_shows_cannot_connect(self, flow):
        with (
            patch("custom_components.myhondaplus.config_flow.DeviceKey"),
            patch("custom_components.myhondaplus.config_flow.HondaAuth"),
        ):
            flow.hass.async_add_executor_job.side_effect = HondaAuthError(
                500, "something-else"
            )
            await flow.async_step_user(
                {
                    "email": "test@test.com",
                    "password": "pass",
                    "scan_interval": 600,
                    "car_refresh_interval": 43200,
                }
            )

        errors = flow.async_show_form.call_args[1]["errors"]
        assert errors["base"] == "cannot_connect"

    @pytest.mark.asyncio
    async def test_generic_exception(self, flow):
        """Unexpected exception shows cannot_connect."""
        with (
            patch("custom_components.myhondaplus.config_flow.DeviceKey"),
            patch("custom_components.myhondaplus.config_flow.HondaAuth"),
        ):
            flow.hass.async_add_executor_job.side_effect = Exception("unexpected")
            await flow.async_step_user(
                {
                    "email": "test@test.com",
                    "password": "pass",
                    "scan_interval": 600,
                    "car_refresh_interval": 43200,
                }
            )

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
        with patch(
            "custom_components.myhondaplus.config_flow.HondaAuth"
        ) as mock_auth_cls:
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

        with (
            patch(
                "custom_components.myhondaplus.config_flow.HondaAuth"
            ) as mock_auth_cls,
            patch("custom_components.myhondaplus.config_flow.HondaAPI") as mock_api_cls,
        ):
            mock_auth_cls.parse_verify_link_key.return_value = ("key123", "link_type")
            mock_auth_cls.extract_user_id.return_value = "fake-user-id"
            mock_api = MagicMock()
            mock_api_cls.return_value = mock_api

            flow.hass.async_add_executor_job.side_effect = [
                None,  # verify_magic_link
                MOCK_TOKENS,  # login
                MOCK_USER_INFO,  # get_user_info
            ]

            await flow.async_step_verify(
                {"verification_link": "https://honda.com/verify?key=abc"}
            )

        flow.async_create_entry.assert_called_once()

    @pytest.mark.asyncio
    async def test_valid_link_failed_login_shows_verification_failed(self, flow):
        flow._email = "test@test.com"
        flow._password = "pass"
        flow._auth = MagicMock()

        with patch(
            "custom_components.myhondaplus.config_flow.HondaAuth"
        ) as mock_auth_cls:
            mock_auth_cls.parse_verify_link_key.return_value = ("key123", "link_type")
            flow.hass.async_add_executor_job.side_effect = [
                None,
                HondaAuthError(401, "invalid-credentials"),
            ]

            await flow.async_step_verify(
                {"verification_link": "https://honda.com/verify?key=abc"}
            )

        errors = flow.async_show_form.call_args[1]["errors"]
        assert errors["base"] == "verification_failed"


class TestOptionsFlow:
    def test_config_flow_returns_options_flow(self):
        assert isinstance(
            MyHondaPlusConfigFlow.async_get_options_flow(MagicMock()),
            MyHondaPlusOptionsFlow,
        )

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

        with patch.object(
            type(flow),
            "config_entry",
            new_callable=lambda: property(lambda self: mock_entry),
        ):
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

        with patch.object(
            type(flow),
            "config_entry",
            new_callable=lambda: property(lambda self: mock_entry),
        ):
            await flow.async_step_init(
                {
                    CONF_SCAN_INTERVAL: 300,
                    CONF_CAR_REFRESH_INTERVAL: 7200,
                }
            )

        flow.hass.config_entries.async_reload.assert_not_called()
        flow.async_create_entry.assert_called_once()
        assert flow.async_create_entry.call_args[1]["data"] == {
            CONF_SCAN_INTERVAL: 300,
            CONF_CAR_REFRESH_INTERVAL: 7200,
        }


class TestReauthFlow:
    @pytest.fixture
    def reauth_flow(self):
        """Create a config flow primed for reauth."""
        f = MyHondaPlusConfigFlow()
        f.hass = MagicMock()
        f.hass.async_add_executor_job = AsyncMock()
        f.hass.config_entries = MagicMock()
        mock_entry = MagicMock()
        mock_entry.data = {
            "email": "test@test.com",
            CONF_VEHICLES: [
                {
                    CONF_VIN: MOCK_VIN,
                    CONF_VEHICLE_NAME: MOCK_VEHICLE_NAME,
                    CONF_FUEL_TYPE: "E",
                }
            ],
        }
        f.hass.config_entries.async_get_entry.return_value = mock_entry
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

        with (
            patch("custom_components.myhondaplus.config_flow.DeviceKey"),
            patch(
                "custom_components.myhondaplus.config_flow.HondaAuth"
            ) as mock_auth_cls,
            patch("custom_components.myhondaplus.config_flow.HondaAPI") as mock_api_cls,
        ):
            mock_auth = MagicMock()
            mock_auth_cls.return_value = mock_auth
            mock_auth_cls.extract_user_id.return_value = "fake-user-id"
            mock_api = MagicMock()
            mock_api_cls.return_value = mock_api
            reauth_flow.hass.async_add_executor_job.side_effect = [
                MOCK_TOKENS,  # login
                MOCK_USER_INFO,  # get_user_info (for reconciliation)
            ]

            await reauth_flow.async_step_reauth_confirm(
                {
                    "email": "test@test.com",
                    "password": "newpass",
                }
            )

        reauth_flow.hass.config_entries.async_update_entry.assert_called_once()
        reauth_flow.async_abort.assert_called_once_with(reason="reauth_successful")

    @pytest.mark.asyncio
    async def test_reauth_invalid_credentials(self, reauth_flow):
        """Bad credentials during reauth show error."""
        reauth_flow.context = {"entry_id": "test_entry"}
        await reauth_flow.async_step_reauth({})

        with (
            patch("custom_components.myhondaplus.config_flow.DeviceKey"),
            patch("custom_components.myhondaplus.config_flow.HondaAuth"),
        ):
            reauth_flow.hass.async_add_executor_job.side_effect = HondaAuthError(
                401, "invalid-credentials"
            )
            await reauth_flow.async_step_reauth_confirm(
                {
                    "email": "test@test.com",
                    "password": "wrong",
                }
            )

        errors = reauth_flow.async_show_form.call_args[1]["errors"]
        assert errors["base"] == "invalid_auth"

    @pytest.mark.asyncio
    async def test_reauth_device_not_registered_goes_to_verify(self, reauth_flow):
        reauth_flow.context = {"entry_id": "test_entry"}
        await reauth_flow.async_step_reauth({})

        with (
            patch("custom_components.myhondaplus.config_flow.DeviceKey"),
            patch(
                "custom_components.myhondaplus.config_flow.HondaAuth"
            ) as mock_auth_cls,
        ):
            mock_auth = MagicMock()
            mock_auth_cls.return_value = mock_auth
            reauth_flow.hass.async_add_executor_job.side_effect = [
                HondaAuthError(401, "device-authenticator-not-registered"),
                None,
            ]

            await reauth_flow.async_step_reauth_confirm(
                {
                    "email": "test@test.com",
                    "password": "newpass",
                }
            )

        assert reauth_flow.async_show_form.call_args[1]["step_id"] == "verify"

    @pytest.mark.asyncio
    async def test_reauth_device_reset_failure_shows_cannot_connect(self, reauth_flow):
        reauth_flow.context = {"entry_id": "test_entry"}
        await reauth_flow.async_step_reauth({})

        with (
            patch("custom_components.myhondaplus.config_flow.DeviceKey"),
            patch(
                "custom_components.myhondaplus.config_flow.HondaAuth"
            ) as mock_auth_cls,
        ):
            mock_auth = MagicMock()
            mock_auth_cls.return_value = mock_auth
            reauth_flow.hass.async_add_executor_job.side_effect = [
                HondaAuthError(401, "device-authenticator-not-registered"),
                HondaAuthError(401, "reset failed"),
            ]

            await reauth_flow.async_step_reauth_confirm(
                {
                    "email": "test@test.com",
                    "password": "newpass",
                }
            )

        errors = reauth_flow.async_show_form.call_args[1]["errors"]
        assert errors["base"] == "cannot_connect"

    @pytest.mark.asyncio
    async def test_reauth_locked_account(self, reauth_flow):
        reauth_flow.context = {"entry_id": "test_entry"}
        await reauth_flow.async_step_reauth({})

        with (
            patch("custom_components.myhondaplus.config_flow.DeviceKey"),
            patch("custom_components.myhondaplus.config_flow.HondaAuth"),
        ):
            reauth_flow.hass.async_add_executor_job.side_effect = HondaAuthError(
                401, "locked-account"
            )
            await reauth_flow.async_step_reauth_confirm(
                {
                    "email": "test@test.com",
                    "password": "wrong",
                }
            )

        errors = reauth_flow.async_show_form.call_args[1]["errors"]
        assert errors["base"] == "account_locked"

    @pytest.mark.asyncio
    async def test_reauth_unknown_honda_auth_error_shows_cannot_connect(
        self, reauth_flow
    ):
        reauth_flow.context = {"entry_id": "test_entry"}
        await reauth_flow.async_step_reauth({})

        with (
            patch("custom_components.myhondaplus.config_flow.DeviceKey"),
            patch("custom_components.myhondaplus.config_flow.HondaAuth"),
        ):
            reauth_flow.hass.async_add_executor_job.side_effect = HondaAuthError(
                500, "something-else"
            )
            await reauth_flow.async_step_reauth_confirm(
                {
                    "email": "test@test.com",
                    "password": "wrong",
                }
            )

        errors = reauth_flow.async_show_form.call_args[1]["errors"]
        assert errors["base"] == "cannot_connect"

    @pytest.mark.asyncio
    async def test_reauth_generic_exception_shows_cannot_connect(self, reauth_flow):
        reauth_flow.context = {"entry_id": "test_entry"}
        await reauth_flow.async_step_reauth({})

        with (
            patch("custom_components.myhondaplus.config_flow.DeviceKey"),
            patch("custom_components.myhondaplus.config_flow.HondaAuth"),
        ):
            reauth_flow.hass.async_add_executor_job.side_effect = Exception(
                "unexpected"
            )
            await reauth_flow.async_step_reauth_confirm(
                {
                    "email": "test@test.com",
                    "password": "wrong",
                }
            )

        errors = reauth_flow.async_show_form.call_args[1]["errors"]
        assert errors["base"] == "cannot_connect"


class TestFetchVehiclesAndCreateEntry:
    @pytest.mark.asyncio
    async def test_fetch_vehicles_reauth_short_circuits(self, flow):
        flow._reauth_entry = MagicMock()
        flow._reauth_entry.data = {"email": "test@test.com", CONF_VEHICLES: []}
        flow._tokens = MOCK_TOKENS
        flow._device_key = MagicMock()
        flow._device_key.pem_bytes = b"fake-pem"
        flow.async_abort = MagicMock(return_value={"type": "abort"})

        with (
            patch(
                "custom_components.myhondaplus.config_flow.HondaAuth"
            ) as mock_auth_cls,
            patch("custom_components.myhondaplus.config_flow.HondaAPI") as mock_api_cls,
        ):
            mock_auth_cls.extract_user_id.return_value = "fake-user-id"
            mock_api = MagicMock()
            mock_api_cls.return_value = mock_api
            flow.hass.async_add_executor_job.side_effect = [MOCK_USER_INFO]

            result = await flow._fetch_vehicles_and_continue()

        assert result == {"type": "abort"}

    @pytest.mark.asyncio
    async def test_fetch_vehicles_unexpected_exception_aborts_cannot_connect(
        self, flow
    ):
        """Unexpected exception during get_user_info aborts the config flow."""
        flow._tokens = MOCK_TOKENS
        flow.async_abort = MagicMock(
            side_effect=lambda reason: {"type": "abort", "reason": reason}
        )

        with (
            patch(
                "custom_components.myhondaplus.config_flow.HondaAuth"
            ) as mock_auth_cls,
            patch("custom_components.myhondaplus.config_flow.HondaAPI") as mock_api_cls,
        ):
            mock_auth_cls.extract_user_id.return_value = "fake-user-id"
            mock_api = MagicMock()
            mock_api_cls.return_value = mock_api
            flow.hass.async_add_executor_job.side_effect = [Exception("boom")]

            result = await flow._fetch_vehicles_and_continue()

        flow.async_abort.assert_called_once_with(reason="cannot_connect")
        assert result == {"type": "abort", "reason": "cannot_connect"}

    @pytest.mark.asyncio
    async def test_fetch_vehicles_api_error_aborts_cannot_connect(self, flow):
        """HondaAPIError during get_user_info aborts cleanly."""
        from pymyhondaplus.api import HondaAPIError

        flow._tokens = MOCK_TOKENS
        flow.async_abort = MagicMock(
            side_effect=lambda reason: {"type": "abort", "reason": reason}
        )

        with (
            patch(
                "custom_components.myhondaplus.config_flow.HondaAuth"
            ) as mock_auth_cls,
            patch("custom_components.myhondaplus.config_flow.HondaAPI") as mock_api_cls,
        ):
            mock_auth_cls.extract_user_id.return_value = "fake-user-id"
            mock_api = MagicMock()
            mock_api_cls.return_value = mock_api
            flow.hass.async_add_executor_job.side_effect = [
                HondaAPIError(503, "service unavailable")
            ]

            result = await flow._fetch_vehicles_and_continue()

        flow.async_abort.assert_called_once_with(reason="cannot_connect")
        assert result == {"type": "abort", "reason": "cannot_connect"}

    @pytest.mark.asyncio
    async def test_fetch_vehicles_empty_list_aborts_no_vehicles(self, flow):
        """Issue #36: empty vehicles list aborts with no_vehicles instead of falling back to manual VIN."""
        flow._tokens = MOCK_TOKENS
        flow.async_abort = MagicMock(
            side_effect=lambda reason: {"type": "abort", "reason": reason}
        )

        with (
            patch(
                "custom_components.myhondaplus.config_flow.HondaAuth"
            ) as mock_auth_cls,
            patch("custom_components.myhondaplus.config_flow.HondaAPI") as mock_api_cls,
        ):
            mock_auth_cls.extract_user_id.return_value = "fake-user-id"
            mock_api = MagicMock()
            mock_api_cls.return_value = mock_api
            flow.hass.async_add_executor_job.side_effect = [
                {"personalId": "p", "vehiclesInfo": []}
            ]

            result = await flow._fetch_vehicles_and_continue()

        flow.async_abort.assert_called_once_with(reason="no_vehicles")
        assert result == {"type": "abort", "reason": "no_vehicles"}

    @pytest.mark.asyncio
    async def test_create_entry_personal_id_fallback(self, flow):
        flow._tokens = MOCK_TOKENS
        flow._email = "test@test.com"
        flow._vehicles = [{"vin": "VIN12345678901234", "name": "", "fuel_type": ""}]
        flow._scan_interval = DEFAULT_SCAN_INTERVAL
        flow._car_refresh_interval = DEFAULT_CAR_REFRESH_INTERVAL
        flow._location_refresh_interval = 3600
        flow._device_key = MagicMock()
        flow._device_key.pem_bytes = b"fake-pem"
        flow._api = None

        with (
            patch(
                "custom_components.myhondaplus.config_flow.HondaAuth"
            ) as mock_auth_cls,
            patch("custom_components.myhondaplus.config_flow.HondaAPI") as mock_api_cls,
        ):
            mock_auth_cls.extract_user_id.return_value = "fake-user-id"
            mock_api = MagicMock()
            mock_api_cls.return_value = mock_api
            flow.hass.async_add_executor_job.side_effect = [Exception("boom")]

            await flow._create_entry()

        flow.async_create_entry.assert_called_once()
        assert "test@test.com" in flow.async_create_entry.call_args[1]["title"]
        assert flow.async_create_entry.call_args[1]["data"]["personal_id"] == ""
        assert (
            flow.async_create_entry.call_args[1]["options"][CONF_SCAN_INTERVAL]
            == DEFAULT_SCAN_INTERVAL
        )


class TestReconcileVehicles:
    def test_new_vin_appended(self):
        existing = [{CONF_VIN: "VIN1", CONF_VEHICLE_NAME: "Car 1", CONF_FUEL_TYPE: "E"}]
        api = [
            {"vin": "VIN1", "name": "Car 1", "fuel_type": "E"},
            {"vin": "VIN2", "name": "Car 2", "fuel_type": "H"},
        ]
        result = _reconcile_vehicles(existing, api)
        assert len(result) == 2
        assert {v[CONF_VIN] for v in result} == {"VIN1", "VIN2"}

    def test_removed_vin_dropped(self):
        existing = [
            {CONF_VIN: "VIN1", CONF_VEHICLE_NAME: "Car 1", CONF_FUEL_TYPE: "E"},
            {CONF_VIN: "VIN2", CONF_VEHICLE_NAME: "Car 2", CONF_FUEL_TYPE: "H"},
        ]
        api = [{"vin": "VIN1", "name": "Car 1", "fuel_type": "E"}]
        result = _reconcile_vehicles(existing, api)
        assert len(result) == 1
        assert result[0][CONF_VIN] == "VIN1"

    def test_manual_vin_preserved(self):
        existing = [
            {
                CONF_VIN: "MANUAL1",
                CONF_VEHICLE_NAME: "",
                CONF_FUEL_TYPE: "",
                "manual": True,
            }
        ]
        api = [{"vin": "VIN1", "name": "Car 1", "fuel_type": "E"}]
        result = _reconcile_vehicles(existing, api)
        assert len(result) == 2
        manual = [v for v in result if v.get("manual")]
        assert len(manual) == 1

    def test_existing_vin_name_updated(self):
        existing = [
            {CONF_VIN: "VIN1", CONF_VEHICLE_NAME: "Old Name", CONF_FUEL_TYPE: "E"}
        ]
        api = [{"vin": "VIN1", "name": "New Name", "fuel_type": "H"}]
        result = _reconcile_vehicles(existing, api)
        assert result[0][CONF_VEHICLE_NAME] == "New Name"
        assert result[0][CONF_FUEL_TYPE] == "H"
