"""Data coordinator for My Honda+."""

import asyncio
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pymyhondaplus.api import (
    HondaAPI,
    HondaAPIError,
    compute_trip_stats,
    parse_charge_schedule,
    parse_climate_schedule,
    parse_ev_status,
)

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_FUEL_TYPE,
    CONF_PERSONAL_ID,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_USER_ID,
    CONF_VIN,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TRIP_INTERVAL,
    DOMAIN,
    LOGGER,
)


def _handle_api_error(
    err: HondaAPIError,
    persist_tokens: callable,
    cached_data: dict | None = None,
) -> dict | None:
    """Handle HondaAPIError consistently across coordinators.

    Returns cached data for transient 5xx errors, raises
    ConfigEntryAuthFailed for 401, or raises UpdateFailed/HomeAssistantError.
    """
    persist_tokens()
    if err.status_code == 401:
        raise ConfigEntryAuthFailed from err
    if err.status_code and err.status_code >= 500 and cached_data is not None:
        LOGGER.warning("Transient server error (%s), keeping cached data", err.status_code)
        return cached_data
    return None


class HondaDataUpdateCoordinator(DataUpdateCoordinator[dict]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.vin: str = entry.data[CONF_VIN]
        self.api = HondaAPI()
        self._apply_tokens()

        interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )

    def _apply_tokens(self) -> None:
        self.api.set_tokens(
            access_token=self.entry.data[CONF_ACCESS_TOKEN],
            refresh_token=self.entry.data[CONF_REFRESH_TOKEN],
            personal_id=self.entry.data.get(CONF_PERSONAL_ID, ""),
            user_id=self.entry.data.get(CONF_USER_ID, ""),
        )

    def _persist_tokens_if_changed(self) -> None:
        tokens = self.api.tokens
        data = self.entry.data
        if (tokens.access_token != data.get(CONF_ACCESS_TOKEN)
                or tokens.refresh_token != data.get(CONF_REFRESH_TOKEN)):
            new_data = {**data,
                        CONF_ACCESS_TOKEN: tokens.access_token,
                        CONF_REFRESH_TOKEN: tokens.refresh_token}
            self.hass.config_entries.async_update_entry(self.entry, data=new_data)

    def _fetch_data(self) -> dict:
        dashboard = self.api.get_dashboard_cached(self.vin)
        data = parse_ev_status(dashboard)
        data["charge_schedule"] = parse_charge_schedule(dashboard)
        data["climate_schedule"] = parse_climate_schedule(dashboard)
        return data

    async def _async_update_data(self) -> dict:
        try:
            data = await self.hass.async_add_executor_job(self._fetch_data)
        except HondaAPIError as err:
            cached = _handle_api_error(
                err, self._persist_tokens_if_changed, self.data,
            )
            if cached is not None:
                return cached
            raise UpdateFailed(str(err)) from err
        except Exception as err:
            raise UpdateFailed(str(err)) from err

        self._persist_tokens_if_changed()
        return data

    def _fetch_data_fresh(self) -> dict:
        dashboard = self.api.get_dashboard(self.vin, fresh=True)
        data = parse_ev_status(dashboard)
        data["charge_schedule"] = parse_charge_schedule(dashboard)
        data["climate_schedule"] = parse_climate_schedule(dashboard)
        return data

    async def async_refresh_from_car(self) -> None:
        """Request fresh data from the car (wakes TCU, polls until done)."""
        try:
            data = await self.hass.async_add_executor_job(self._fetch_data_fresh)
        except HondaAPIError as err:
            _handle_api_error(err, self._persist_tokens_if_changed)
            LOGGER.error("Dashboard refresh failed: %s", err)
            raise HomeAssistantError(
                "Unable to refresh data from vehicle"
            ) from err
        self._persist_tokens_if_changed()
        self.async_set_updated_data(data)

    async def async_send_command(self, func, *args) -> str:
        try:
            result = await self.hass.async_add_executor_job(func, *args)
        except HondaAPIError as err:
            _handle_api_error(err, self._persist_tokens_if_changed)
            LOGGER.error("Remote command failed: %s", err)
            raise HomeAssistantError(
                "Unable to send command to vehicle"
            ) from err
        self._persist_tokens_if_changed()
        return result

    async def _async_poll_command(self, command_id: str, timeout: int = 60) -> bool:
        """Poll a command until confirmed or timeout. Returns True if confirmed."""
        if not command_id:
            return False
        polls = timeout // 2
        for _ in range(polls):
            result = await self.hass.async_add_executor_job(
                self.api.poll_command, command_id,
            )
            if result["status_code"] == 200:
                return True
            await asyncio.sleep(2)
        return False

    async def async_send_command_and_wait(self, func, *args, timeout: int = 60) -> bool:
        """Send a command and wait for confirmation. Raises on send failure."""
        command_id = await self.async_send_command(func, *args)
        confirmed = await self._async_poll_command(command_id, timeout)
        if not confirmed:
            LOGGER.warning("Command timed out waiting for confirmation (id=%s)", command_id)
        return confirmed


class HondaTripCoordinator(DataUpdateCoordinator[dict]):

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: HondaAPI,
        persist_tokens: callable,
        main_coordinator: HondaDataUpdateCoordinator | None = None,
    ) -> None:
        self.entry = entry
        self.vin: str = entry.data[CONF_VIN]
        self.api = api
        self._persist_tokens = persist_tokens
        self._main_coordinator = main_coordinator
        self._fuel_type: str = entry.data.get(CONF_FUEL_TYPE, "")

        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_trips",
            update_interval=timedelta(seconds=DEFAULT_TRIP_INTERVAL),
        )

    def _fetch_data(self) -> dict:
        rows = self.api.get_all_trips(self.vin)
        distance_unit = "km"
        if self._main_coordinator and self._main_coordinator.data:
            distance_unit = self._main_coordinator.data.get("distance_unit", "km")
        return compute_trip_stats(
            rows, "month", fuel_type=self._fuel_type, distance_unit=distance_unit,
        )

    async def _async_update_data(self) -> dict:
        try:
            data = await self.hass.async_add_executor_job(self._fetch_data)
        except HondaAPIError as err:
            cached = _handle_api_error(
                err, self._persist_tokens, self.data,
            )
            if cached is not None:
                return cached
            raise UpdateFailed(str(err)) from err
        except Exception as err:
            raise UpdateFailed(str(err)) from err

        self._persist_tokens()
        return data
