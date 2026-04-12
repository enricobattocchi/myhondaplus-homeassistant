"""Data coordinator for My Honda+."""

from dataclasses import dataclass, field, fields
from datetime import timedelta

from homeassistant.components.persistent_notification import (
    async_create as pn_async_create,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pymyhondaplus.api import (
    EVStatus,
    HondaAPI,
    HondaAPIError,
    HondaAuthError,
    compute_trip_stats,
    parse_charge_schedule,
    parse_climate_schedule,
    parse_ev_status,
)

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TRIP_INTERVAL,
    DOMAIN,
    LOGGER,
)
from .entry_options import get_entry_value


@dataclass
class DashboardData(EVStatus):
    """Vehicle dashboard data: EVStatus fields plus parsed schedules."""

    charge_schedule: list[dict] = field(default_factory=list)
    climate_schedule: list[dict] = field(default_factory=list)


def _handle_api_error(
    err: HondaAPIError,
    persist_tokens: callable,
    cached_data=None,
):
    """Handle HondaAPIError consistently across coordinators.

    Returns cached data for transient 5xx errors, raises
    ConfigEntryAuthFailed for auth errors, or raises UpdateFailed/HomeAssistantError.
    """
    persist_tokens()
    if isinstance(err, HondaAuthError):
        raise ConfigEntryAuthFailed from err
    if err.status_code and err.status_code >= 500 and cached_data is not None:
        return cached_data
    return None


class HondaDataUpdateCoordinator(DataUpdateCoordinator[DashboardData]):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: HondaAPI,
        vin: str,
        vehicle_name: str = "",
    ) -> None:
        self.entry = entry
        self.vin: str = vin
        self._vehicle_name: str = vehicle_name
        self.api = api
        self._service_available = True

        interval = get_entry_value(entry, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_{vin[-6:]}",
            update_interval=timedelta(seconds=interval),
        )

    def _persist_tokens_if_changed(self) -> None:
        tokens = self.api.tokens
        data = self.entry.data
        if tokens.access_token != data.get(
            CONF_ACCESS_TOKEN
        ) or tokens.refresh_token != data.get(CONF_REFRESH_TOKEN):
            new_data = {
                **data,
                CONF_ACCESS_TOKEN: tokens.access_token,
                CONF_REFRESH_TOKEN: tokens.refresh_token,
            }
            self.hass.config_entries.async_update_entry(self.entry, data=new_data)

    def _fetch_data(self) -> DashboardData:
        dashboard = self.api.get_dashboard_cached(self.vin)
        ev = parse_ev_status(dashboard)
        ev_values = {f.name: getattr(ev, f.name) for f in fields(ev)}
        return DashboardData(
            **ev_values,
            charge_schedule=parse_charge_schedule(dashboard),
            climate_schedule=parse_climate_schedule(dashboard),
        )

    def _log_unavailable_once(self, message: str, *args) -> None:
        """Log when the Honda service becomes unavailable."""
        if self._service_available:
            LOGGER.warning(message, *args)
            self._service_available = False

    def _log_recovered_once(self) -> None:
        """Log when the Honda service becomes available again."""
        if not self._service_available:
            LOGGER.info("Connection to Honda API restored")
            self._service_available = True

    async def _async_update_data(self) -> DashboardData:
        try:
            data = await self.hass.async_add_executor_job(self._fetch_data)
        except HondaAPIError as err:
            cached = _handle_api_error(
                err,
                self._persist_tokens_if_changed,
                self.data,
            )
            if cached is not None:
                self._log_unavailable_once(
                    "Honda API unavailable (%s), keeping cached vehicle data",
                    err.status_code,
                )
                return cached
            self._log_unavailable_once("Honda API unavailable: %s", err)
            raise UpdateFailed(str(err)) from err
        except Exception as err:
            self._log_unavailable_once("Honda API unavailable: %s", err)
            raise UpdateFailed(str(err)) from err

        self._persist_tokens_if_changed()
        self._log_recovered_once()
        return data

    def _refresh_from_car(self):
        """Request fresh data from the car and return the command result."""
        return self.api.refresh_dashboard(self.vin)

    async def async_refresh_from_car(self, *, notify_on_timeout: bool = True) -> None:
        """Request fresh data from the car (wakes TCU, polls until done)."""
        try:
            result = await self.hass.async_add_executor_job(self._refresh_from_car)
            if not result.success:
                if result.timed_out:
                    LOGGER.warning(
                        "Dashboard refresh timed out waiting for the car to respond (status=%s, reason=%s)",
                        result.status,
                        result.reason,
                    )
                    if notify_on_timeout:
                        pn_async_create(
                            self.hass,
                            f"Dashboard refresh for {self._vehicle_name or self.vin} timed out waiting for the car to respond.",
                            title="My Honda+",
                            notification_id=f"{DOMAIN}_refresh_timeout",
                        )
                else:
                    LOGGER.warning(
                        "Dashboard refresh did not succeed (status=%s, reason=%s)",
                        result.status,
                        result.reason,
                    )
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="refresh_data_failed",
                )
            data = await self.hass.async_add_executor_job(self._fetch_data)
        except HondaAPIError as err:
            _handle_api_error(err, self._persist_tokens_if_changed)
            LOGGER.error("Dashboard refresh failed: %s", err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="refresh_data_failed",
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
                translation_domain=DOMAIN,
                translation_key="send_command_failed",
            ) from err
        self._persist_tokens_if_changed()
        return result

    async def async_send_command_and_wait(
        self,
        func,
        *args,
        timeout: int = 90,
        notify_on_timeout: bool = True,
    ) -> bool:
        """Send a command and wait for confirmation. Raises on send failure."""
        command_id = await self.async_send_command(func, *args)
        if not command_id:
            return False
        result = await self.hass.async_add_executor_job(
            self.api.wait_for_command,
            command_id,
            timeout,
        )
        if not result.success:
            if result.timed_out:
                LOGGER.warning(
                    "Command timed out waiting for the car to respond (id=%s, status=%s, reason=%s)",
                    command_id,
                    result.status,
                    result.reason,
                )
                if notify_on_timeout:
                    pn_async_create(
                        self.hass,
                        f"A command for {self._vehicle_name or self.vin} timed out waiting for the car to respond.",
                        title="My Honda+",
                        notification_id=f"{DOMAIN}_command_timeout",
                    )
            else:
                LOGGER.warning(
                    "Command did not succeed (id=%s, status=%s, reason=%s)",
                    command_id,
                    result.status,
                    result.reason,
                )
        return result.success

    async def async_refresh_location(self, *, notify_on_timeout: bool = True) -> None:
        """Request fresh GPS location from the car and update dashboard."""
        try:
            command_id = await self.async_send_command(
                self.api.request_car_location,
                self.vin,
            )
            result = await self.hass.async_add_executor_job(
                self.api.wait_for_command,
                command_id,
                90,
            )
            if not result.success:
                if result.timed_out:
                    LOGGER.warning(
                        "Location refresh timed out waiting for the car to respond (id=%s, status=%s, reason=%s)",
                        command_id,
                        result.status,
                        result.reason,
                    )
                    if notify_on_timeout:
                        pn_async_create(
                            self.hass,
                            f"Location refresh for {self._vehicle_name or self.vin} timed out waiting for the car to respond.",
                            title="My Honda+",
                            notification_id=f"{DOMAIN}_location_timeout",
                        )
                else:
                    LOGGER.warning(
                        "Location refresh command did not succeed (id=%s, status=%s, reason=%s)",
                        command_id,
                        result.status,
                        result.reason,
                    )
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="refresh_location_failed",
                )
            data = await self.hass.async_add_executor_job(self._fetch_data)
        except HondaAPIError as err:
            _handle_api_error(err, self._persist_tokens_if_changed)
            LOGGER.error("Location refresh failed: %s", err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="refresh_location_failed",
            ) from err
        self._persist_tokens_if_changed()
        self.async_set_updated_data(data)


class HondaTripCoordinator(DataUpdateCoordinator[dict]):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: HondaAPI,
        persist_tokens: callable,
        vin: str,
        fuel_type: str = "",
        main_coordinator: HondaDataUpdateCoordinator | None = None,
    ) -> None:
        self.entry = entry
        self.vin: str = vin
        self.api = api
        self._persist_tokens = persist_tokens
        self._main_coordinator = main_coordinator
        self._fuel_type: str = fuel_type
        self._service_available = True

        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_trips_{vin[-6:]}",
            update_interval=timedelta(seconds=DEFAULT_TRIP_INTERVAL),
        )

    def _fetch_data(self) -> dict:
        rows = self.api.get_all_trips(self.vin)
        distance_unit = "km"
        if self._main_coordinator and self._main_coordinator.data:
            distance_unit = self._main_coordinator.data.distance_unit
        return compute_trip_stats(
            rows,
            "month",
            fuel_type=self._fuel_type,
            distance_unit=distance_unit,
        )

    def _log_unavailable_once(self, message: str, *args) -> None:
        """Log when the Honda service becomes unavailable."""
        if self._service_available:
            LOGGER.warning(message, *args)
            self._service_available = False

    def _log_recovered_once(self) -> None:
        """Log when the Honda service becomes available again."""
        if not self._service_available:
            LOGGER.info("Connection to Honda API restored")
            self._service_available = True

    async def _async_update_data(self) -> dict:
        try:
            data = await self.hass.async_add_executor_job(self._fetch_data)
        except HondaAPIError as err:
            cached = _handle_api_error(
                err,
                self._persist_tokens,
                self.data,
            )
            if cached is not None:
                self._log_unavailable_once(
                    "Honda API unavailable (%s), keeping cached trip data",
                    err.status_code,
                )
                return cached
            self._log_unavailable_once("Honda API unavailable: %s", err)
            raise UpdateFailed(str(err)) from err
        except Exception as err:
            self._log_unavailable_once("Honda API unavailable: %s", err)
            raise UpdateFailed(str(err)) from err

        self._persist_tokens()
        self._log_recovered_once()
        return data
