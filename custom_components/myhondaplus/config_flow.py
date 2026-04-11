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
    CONF_LOCATION_REFRESH_INTERVAL,
    CONF_MODEL,
    CONF_PERSONAL_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_ID,
    CONF_VEHICLE_NAME,
    CONF_VEHICLES,
    CONF_VIN,
    DEFAULT_CAR_REFRESH_INTERVAL,
    DEFAULT_LOCATION_REFRESH_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
)
from .entry_options import get_entry_value

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
        vol.Optional(
            CONF_CAR_REFRESH_INTERVAL, default=DEFAULT_CAR_REFRESH_INTERVAL
        ): int,
        vol.Optional(
            CONF_LOCATION_REFRESH_INTERVAL, default=DEFAULT_LOCATION_REFRESH_INTERVAL
        ): int,
    }
)

STEP_VERIFY_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("verification_link"): str,
    }
)

STEP_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class MyHondaPlusOptionsFlow(config_entries.OptionsFlow):
    """Options flow for My Honda+."""

    async def async_step_init(self, user_input=None):
        """Handle options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=get_entry_value(
                            self.config_entry,
                            CONF_SCAN_INTERVAL,
                            DEFAULT_SCAN_INTERVAL,
                        ),
                    ): int,
                    vol.Optional(
                        CONF_CAR_REFRESH_INTERVAL,
                        default=get_entry_value(
                            self.config_entry,
                            CONF_CAR_REFRESH_INTERVAL,
                            DEFAULT_CAR_REFRESH_INTERVAL,
                        ),
                    ): int,
                    vol.Optional(
                        CONF_LOCATION_REFRESH_INTERVAL,
                        default=get_entry_value(
                            self.config_entry,
                            CONF_LOCATION_REFRESH_INTERVAL,
                            DEFAULT_LOCATION_REFRESH_INTERVAL,
                        ),
                    ): int,
                }
            ),
        )


class MyHondaPlusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 3

    @staticmethod
    def async_get_options_flow(config_entry):
        return MyHondaPlusOptionsFlow()

    def __init__(self):
        self._email = None
        self._password = None
        self._scan_interval = DEFAULT_SCAN_INTERVAL
        self._car_refresh_interval = DEFAULT_CAR_REFRESH_INTERVAL
        self._location_refresh_interval = DEFAULT_LOCATION_REFRESH_INTERVAL
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
            self._scan_interval = user_input.get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            )
            self._car_refresh_interval = user_input.get(
                CONF_CAR_REFRESH_INTERVAL, DEFAULT_CAR_REFRESH_INTERVAL
            )
            self._location_refresh_interval = user_input.get(
                CONF_LOCATION_REFRESH_INTERVAL,
                DEFAULT_LOCATION_REFRESH_INTERVAL,
            )

            self._device_key = DeviceKey()
            self._auth = HondaAuth(device_key=self._device_key)

            try:
                self._tokens = await self.hass.async_add_executor_job(
                    self._auth.login,
                    self._email,
                    self._password,
                )
                return await self._fetch_vehicles_and_continue()
            except HondaAuthError as e:
                error_text = str(e)
                if "device-authenticator-not-registered" in error_text:
                    try:
                        await self.hass.async_add_executor_job(
                            self._auth.reset_device_authenticator,
                            self._email,
                            self._password,
                        )
                    except HondaAuthError as e2:
                        if "currently blocked" not in str(e2):
                            errors["base"] = "cannot_connect"
                            return self._show_user_form(errors)

                    return await self.async_step_verify()
                elif (
                    "invalid-credentials" in error_text.lower()
                    or "INVALID_CREDS" in error_text
                ):
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
                    self._auth.login,
                    self._email,
                    self._password,
                )
                return await self._update_reauth_entry()
            except HondaAuthError as e:
                error_text = str(e)
                if "device-authenticator-not-registered" in error_text:
                    try:
                        await self.hass.async_add_executor_job(
                            self._auth.reset_device_authenticator,
                            self._email,
                            self._password,
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
                elif (
                    "invalid-credentials" in error_text.lower()
                    or "INVALID_CREDS" in error_text
                ):
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

    async def _update_reauth_entry(self):
        """Update the existing config entry with new tokens and refreshed vehicle list."""
        user_id = HondaAuth.extract_user_id(self._tokens["access_token"])
        new_data = {
            **self._reauth_entry.data,
            CONF_ACCESS_TOKEN: self._tokens["access_token"],
            CONF_REFRESH_TOKEN: self._tokens["refresh_token"],
            CONF_USER_ID: user_id,
            CONF_DEVICE_KEY_PEM: self._device_key.pem_bytes.decode(),
        }

        # Refresh vehicle list during reauth
        api = HondaAPI()
        api.set_tokens(
            access_token=self._tokens["access_token"],
            refresh_token=self._tokens["refresh_token"],
            user_id=user_id,
        )
        try:
            user_info = await self.hass.async_add_executor_job(api.get_user_info)
            api_vehicles = _parse_vehicles(user_info)
            new_data[CONF_VEHICLES] = _reconcile_vehicles(
                new_data.get(CONF_VEHICLES, []),
                api_vehicles,
            )
        except Exception:
            LOGGER.warning("Could not refresh vehicle list during reauth")

        self.hass.config_entries.async_update_entry(
            self._reauth_entry,
            data=new_data,
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
                    self._auth.verify_magic_link,
                    key,
                    link_type,
                )

                try:
                    self._tokens = await self.hass.async_add_executor_job(
                        self._auth.login,
                        self._email,
                        self._password,
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
        """After login, fetch vehicles and create entry.

        During reauth, skip vehicle selection and just update tokens.
        """
        if self._reauth_entry is not None:
            return await self._update_reauth_entry()
        user_id = HondaAuth.extract_user_id(self._tokens["access_token"])

        self._api = HondaAPI()
        self._api.set_tokens(
            access_token=self._tokens["access_token"],
            refresh_token=self._tokens["refresh_token"],
            user_id=user_id,
        )

        try:
            user_info = await self.hass.async_add_executor_job(
                self._api.get_user_info,
            )
            self._personal_id = str(user_info.get("personalId", ""))
            self._vehicles = _parse_vehicles(user_info)
        except Exception:
            LOGGER.exception("Failed to fetch vehicles")
            self._personal_id = ""
            self._vehicles = []

        if self._vehicles:
            return await self._create_entry()

        # No vehicles found — fall back to manual VIN entry
        return await self.async_step_manual_vin()

    async def async_step_manual_vin(self, user_input=None):
        """Fallback: manual VIN entry if vehicle discovery fails."""
        if user_input is not None:
            self._vehicles = [
                {
                    "vin": user_input[CONF_VIN],
                    "name": "",
                    "fuel_type": "",
                    "manual": True,
                }
            ]
            return await self._create_entry()

        return self.async_show_form(
            step_id="manual_vin",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_VIN): str,
                }
            ),
        )

    async def _create_entry(self):
        user_id = HondaAuth.extract_user_id(self._tokens["access_token"])

        if self._api is None:
            self._api = HondaAPI()
            self._api.set_tokens(
                access_token=self._tokens["access_token"],
                refresh_token=self._tokens["refresh_token"],
                user_id=user_id,
            )

        personal_id = getattr(self, "_personal_id", "") or ""
        if not personal_id:
            try:
                info = await self.hass.async_add_executor_job(
                    self._api.get_user_info,
                    user_id,
                )
                personal_id = str(info.get("personalId", ""))
            except Exception:
                personal_id = ""

        await self.async_set_unique_id(self._email.lower())
        self._abort_if_unique_id_configured()

        vehicles = [
            {
                CONF_VIN: v["vin"],
                CONF_VEHICLE_NAME: v.get("name", ""),
                CONF_FUEL_TYPE: v.get("fuel_type", ""),
                CONF_MODEL: v.get("model", ""),
                **({"manual": True} if v.get("manual") else {}),
            }
            for v in self._vehicles
        ]

        title = f"My Honda+ ({self._email})"

        return self.async_create_entry(
            title=title,
            data={
                CONF_EMAIL: self._email,
                CONF_ACCESS_TOKEN: self._tokens["access_token"],
                CONF_REFRESH_TOKEN: self._tokens["refresh_token"],
                CONF_USER_ID: user_id,
                CONF_PERSONAL_ID: personal_id,
                CONF_DEVICE_KEY_PEM: self._device_key.pem_bytes.decode(),
                CONF_VEHICLES: vehicles,
            },
            options={
                CONF_SCAN_INTERVAL: self._scan_interval,
                CONF_CAR_REFRESH_INTERVAL: self._car_refresh_interval,
                CONF_LOCATION_REFRESH_INTERVAL: self._location_refresh_interval,
            },
        )


def _build_model_name(v: dict) -> str:
    """Build a display model name from raw vehiclesInfo fields."""
    ui = v.get("vehicleUIConfiguration", {})
    friendly = ui.get("friendlyModelName", "")
    grade = v.get("grade", "")
    year = v.get("modelYear")

    if friendly and grade:
        parts = grade.split(None, 1)
        grade = (
            parts[1].title() if len(parts) > 1 and len(parts[0]) <= 2 else grade.title()
        )

    name = friendly
    if grade:
        name = f"{name} {grade}" if name else grade
    if year:
        name = f"{name} ({year})" if name else str(year)
    return name


def _parse_vehicles(user_info: dict) -> list[dict]:
    """Parse vehiclesInfo from get_user_info into our vehicle format."""
    return [
        {
            "vin": v["vin"],
            "name": v.get("vehicleNickName", ""),
            "fuel_type": v.get("fuelType", ""),
            "model": _build_model_name(v),
        }
        for v in user_info.get("vehiclesInfo", [])
        if "vin" in v
    ]


def _reconcile_vehicles(
    existing: list[dict],
    api_vehicles: list[dict],
) -> list[dict]:
    """Reconcile existing vehicle list with freshly discovered vehicles.

    - New VINs from API → appended
    - Existing VINs → name/fuel_type/model updated from API
    - Manual VINs → always preserved
    - VINs previously from API but no longer returned → removed
    """
    api_by_vin = {v["vin"]: v for v in api_vehicles}
    result = []

    for v in existing:
        vin = v[CONF_VIN]
        if v.get("manual"):
            # Manual VINs always preserved
            result.append(v)
        elif vin in api_by_vin:
            # Update name/fuel_type from API
            api_v = api_by_vin.pop(vin)
            result.append(
                {
                    **v,
                    CONF_VEHICLE_NAME: api_v.get("name", v.get(CONF_VEHICLE_NAME, "")),
                    CONF_FUEL_TYPE: api_v.get("fuel_type", v.get(CONF_FUEL_TYPE, "")),
                    CONF_MODEL: api_v.get("model", v.get(CONF_MODEL, "")),
                }
            )
        # else: VIN no longer in API → removed

    # Append newly discovered VINs
    for vin, api_v in api_by_vin.items():
        if not any(v[CONF_VIN] == vin for v in result):
            result.append(
                {
                    CONF_VIN: vin,
                    CONF_VEHICLE_NAME: api_v.get("name", ""),
                    CONF_FUEL_TYPE: api_v.get("fuel_type", ""),
                    CONF_MODEL: api_v.get("model", ""),
                }
            )

    return result
