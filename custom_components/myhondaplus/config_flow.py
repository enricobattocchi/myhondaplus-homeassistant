"""Config flow for My Honda+."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_SCAN_INTERVAL
from pymyhondaplus.api import HondaAPI, HondaAuthError
from pymyhondaplus.auth import DeviceKey, HondaAuth

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CAR_REFRESH_INTERVAL,
    CONF_DEVICE_KEY_PEM,
    CONF_FUEL_TYPE,
    CONF_PERSONAL_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_ID,
    CONF_VEHICLE_NAME,
    CONF_VIN,
    DEFAULT_CAR_REFRESH_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_EMAIL): str,
    vol.Required(CONF_PASSWORD): str,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
    vol.Optional(CONF_CAR_REFRESH_INTERVAL, default=DEFAULT_CAR_REFRESH_INTERVAL): int,
})

STEP_VERIFY_DATA_SCHEMA = vol.Schema({
    vol.Required("verification_link"): str,
})

STEP_REAUTH_SCHEMA = vol.Schema({
    vol.Required(CONF_EMAIL): str,
    vol.Required(CONF_PASSWORD): str,
})


class MyHondaPlusOptionsFlow(config_entries.OptionsFlow):
    """Options flow for My Honda+."""

    async def async_step_init(self, user_input=None):
        """Handle options."""
        if user_input is not None:
            # Store options in entry data so coordinators pick them up
            new_data = {**self.config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data,
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.data.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL,
                    ),
                ): int,
                vol.Optional(
                    CONF_CAR_REFRESH_INTERVAL,
                    default=self.config_entry.data.get(
                        CONF_CAR_REFRESH_INTERVAL, DEFAULT_CAR_REFRESH_INTERVAL,
                    ),
                ): int,
            }),
        )


class MyHondaPlusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        return MyHondaPlusOptionsFlow()

    def __init__(self):
        self._email = None
        self._password = None
        self._scan_interval = DEFAULT_SCAN_INTERVAL
        self._car_refresh_interval = DEFAULT_CAR_REFRESH_INTERVAL
        self._device_key = None
        self._auth = None
        self._tokens = None
        self._api = None
        self._vehicles = []
        self._reauth_entry = None

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            self._email = user_input[CONF_EMAIL]
            self._password = user_input[CONF_PASSWORD]
            self._scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            self._car_refresh_interval = user_input.get(CONF_CAR_REFRESH_INTERVAL, DEFAULT_CAR_REFRESH_INTERVAL)

            self._device_key = DeviceKey()
            self._auth = HondaAuth(device_key=self._device_key)

            try:
                self._tokens = await self.hass.async_add_executor_job(
                    self._auth.login, self._email, self._password,
                )
                return await self._fetch_vehicles_and_continue()
            except HondaAuthError as e:
                error_text = str(e)
                if "device-authenticator-not-registered" in error_text:
                    try:
                        await self.hass.async_add_executor_job(
                            self._auth.reset_device_authenticator,
                            self._email, self._password,
                        )
                    except HondaAuthError as e2:
                        if "currently blocked" not in str(e2):
                            errors["base"] = "cannot_connect"
                            return self._show_user_form(errors)

                    return await self.async_step_verify()
                elif "invalid-credentials" in error_text.lower() or "INVALID_CREDS" in error_text:
                    errors["base"] = "invalid_auth"
                elif "locked-account" in error_text.lower():
                    errors["base"] = "account_locked"
                else:
                    LOGGER.error("Login failed: %s", e)
                    errors["base"] = "cannot_connect"
            except Exception:
                LOGGER.exception("Unexpected error during login")
                errors["base"] = "cannot_connect"

        return self._show_user_form(errors)

    async def async_step_reauth(self, entry_data):
        """Handle reauth when tokens expire."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"],
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Handle reauth confirmation."""
        errors = {}
        if user_input is not None:
            self._email = user_input[CONF_EMAIL]
            self._password = user_input[CONF_PASSWORD]
            self._device_key = DeviceKey()
            self._auth = HondaAuth(device_key=self._device_key)

            try:
                self._tokens = await self.hass.async_add_executor_job(
                    self._auth.login, self._email, self._password,
                )
                return self._update_reauth_entry()
            except HondaAuthError as e:
                error_text = str(e)
                if "device-authenticator-not-registered" in error_text:
                    try:
                        await self.hass.async_add_executor_job(
                            self._auth.reset_device_authenticator,
                            self._email, self._password,
                        )
                    except HondaAuthError as e2:
                        if "currently blocked" not in str(e2):
                            errors["base"] = "cannot_connect"
                            return self.async_show_form(
                                step_id="reauth_confirm",
                                data_schema=STEP_REAUTH_SCHEMA,
                                errors=errors,
                            )
                    return await self.async_step_verify()
                elif "invalid-credentials" in error_text.lower() or "INVALID_CREDS" in error_text:
                    errors["base"] = "invalid_auth"
                elif "locked-account" in error_text.lower():
                    errors["base"] = "account_locked"
                else:
                    LOGGER.error("Reauth login failed: %s", e)
                    errors["base"] = "cannot_connect"
            except Exception:
                LOGGER.exception("Unexpected error during reauth")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_SCHEMA,
            errors=errors,
        )

    def _update_reauth_entry(self):
        """Update the existing config entry with new tokens."""
        user_id = HondaAuth.extract_user_id(self._tokens["access_token"])
        new_data = {
            **self._reauth_entry.data,
            CONF_ACCESS_TOKEN: self._tokens["access_token"],
            CONF_REFRESH_TOKEN: self._tokens["refresh_token"],
            CONF_USER_ID: user_id,
            CONF_DEVICE_KEY_PEM: self._device_key.pem_bytes.decode(),
        }
        self.hass.config_entries.async_update_entry(
            self._reauth_entry, data=new_data,
        )
        return self.async_abort(reason="reauth_successful")

    def _show_user_form(self, errors=None):
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors or {},
        )

    async def async_step_verify(self, user_input=None):
        errors = {}

        if user_input is not None:
            link = user_input["verification_link"].strip()
            key, link_type = HondaAuth.parse_verify_link_key(link)

            if not key:
                errors["base"] = "invalid_link"
            else:
                await self.hass.async_add_executor_job(
                    self._auth.verify_magic_link, key, link_type,
                )

                try:
                    self._tokens = await self.hass.async_add_executor_job(
                        self._auth.login, self._email, self._password,
                    )
                    return await self._fetch_vehicles_and_continue()
                except HondaAuthError as e:
                    LOGGER.error("Login after verification failed: %s", e)
                    errors["base"] = "verification_failed"

        return self.async_show_form(
            step_id="verify",
            data_schema=STEP_VERIFY_DATA_SCHEMA,
            errors=errors,
        )

    async def _fetch_vehicles_and_continue(self):
        """After login, fetch vehicles and go to selection or create entry.

        During reauth, skip vehicle selection and just update tokens.
        """
        if self._reauth_entry is not None:
            return self._update_reauth_entry()
        user_id = HondaAuth.extract_user_id(self._tokens["access_token"])

        self._api = HondaAPI()
        self._api.set_tokens(
            access_token=self._tokens["access_token"],
            refresh_token=self._tokens["refresh_token"],
            user_id=user_id,
        )

        try:
            self._vehicles = await self.hass.async_add_executor_job(
                self._api.get_vehicles,
            )
        except Exception:
            LOGGER.exception("Failed to fetch vehicles")
            self._vehicles = []

        if len(self._vehicles) == 1:
            return await self._create_entry(
                self._vehicles[0]["vin"],
                self._vehicles[0].get("name", ""),
                self._vehicles[0].get("fuel_type", ""),
            )

        if len(self._vehicles) > 1:
            return await self.async_step_select_vehicle()

        # No vehicles found — fall back to manual VIN entry
        return await self.async_step_manual_vin()

    async def async_step_select_vehicle(self, user_input=None):
        """Let user pick a vehicle from their account."""
        if user_input is not None:
            vin = user_input[CONF_VIN]
            vehicle = next((v for v in self._vehicles if v["vin"] == vin), {})
            return await self._create_entry(
                vin, vehicle.get("name", ""), vehicle.get("fuel_type", ""),
            )

        options = {
            v["vin"]: f"{v.get('name') or v['vin']} ({v['plate']})"
            if v.get("plate")
            else v.get("name") or v["vin"]
            for v in self._vehicles
        }

        return self.async_show_form(
            step_id="select_vehicle",
            data_schema=vol.Schema({
                vol.Required(CONF_VIN): vol.In(options),
            }),
        )

    async def async_step_manual_vin(self, user_input=None):
        """Fallback: manual VIN entry if vehicle discovery fails."""
        if user_input is not None:
            return await self._create_entry(user_input[CONF_VIN], "", "")

        return self.async_show_form(
            step_id="manual_vin",
            data_schema=vol.Schema({
                vol.Required(CONF_VIN): str,
            }),
        )

    async def _create_entry(self, vin: str, vehicle_name: str, fuel_type: str):
        user_id = HondaAuth.extract_user_id(self._tokens["access_token"])

        if self._api is None:
            self._api = HondaAPI()
            self._api.set_tokens(
                access_token=self._tokens["access_token"],
                refresh_token=self._tokens["refresh_token"],
                user_id=user_id,
            )

        try:
            info = await self.hass.async_add_executor_job(
                self._api.get_user_info, user_id,
            )
            personal_id = str(info.get("personalId", ""))
        except Exception:
            personal_id = ""

        await self.async_set_unique_id(vin)
        self._abort_if_unique_id_configured()

        title = vehicle_name or f"Honda {vin[-6:]}"

        return self.async_create_entry(
            title=title,
            data={
                CONF_EMAIL: self._email,
                CONF_VIN: vin,
                CONF_VEHICLE_NAME: vehicle_name,
                CONF_SCAN_INTERVAL: self._scan_interval,
                CONF_CAR_REFRESH_INTERVAL: self._car_refresh_interval,
                CONF_ACCESS_TOKEN: self._tokens["access_token"],
                CONF_REFRESH_TOKEN: self._tokens["refresh_token"],
                CONF_USER_ID: user_id,
                CONF_PERSONAL_ID: personal_id,
                CONF_DEVICE_KEY_PEM: self._device_key.pem_bytes.decode(),
                CONF_FUEL_TYPE: fuel_type,
            },
        )
