"""My Honda+ integration for Home Assistant."""

import voluptuous as vol
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.event import async_call_later

from .const import (
    CONF_CAR_REFRESH_INTERVAL,
    DEFAULT_CAR_REFRESH_INTERVAL,
    DOMAIN,
    LOGGER,
)
from .coordinator import HondaDataUpdateCoordinator, HondaTripCoordinator
from .data import MyHondaPlusConfigEntry, MyHondaPlusData

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.DEVICE_TRACKER, Platform.LOCK, Platform.NUMBER, Platform.SELECT, Platform.SENSOR, Platform.SWITCH]

SERVICE_SET_CHARGE_SCHEDULE = "set_charge_schedule"
SERVICE_SET_CLIMATE_SCHEDULE = "set_climate_schedule"
SERVICE_CLIMATE_ON = "climate_on"

CHARGE_RULE_SCHEMA = vol.Schema({
    vol.Required("days"): str,
    vol.Required("location"): vol.In(["home", "all"]),
    vol.Required("start_time"): str,
    vol.Required("end_time"): str,
    vol.Optional("enabled", default=True): bool,
})

CLIMATE_RULE_SCHEMA = vol.Schema({
    vol.Required("days"): str,
    vol.Required("start_time"): str,
    vol.Optional("enabled", default=True): bool,
})

SERVICE_CLIMATE_ON_SCHEMA = vol.Schema({
    vol.Optional("temp", default="normal"): vol.In(["cooler", "normal", "hotter"]),
    vol.Optional("duration", default=30): vol.In([10, 20, 30]),
    vol.Optional("defrost", default=True): bool,
})
SERVICE_CHARGE_SCHEDULE_SCHEMA = vol.Schema({
    vol.Required("rules"): [CHARGE_RULE_SCHEMA],
})
SERVICE_CLIMATE_SCHEDULE_SCHEMA = vol.Schema({
    vol.Required("rules"): [CLIMATE_RULE_SCHEMA],
})


async def async_setup_entry(hass: HomeAssistant, entry: MyHondaPlusConfigEntry) -> bool:
    """Set up My Honda+ from a config entry."""
    coordinator = HondaDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    trip_coordinator = HondaTripCoordinator(
        hass, entry, coordinator.api, coordinator._persist_tokens_if_changed,
        main_coordinator=coordinator,
    )
    await trip_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = MyHondaPlusData(
        coordinator=coordinator,
        trip_coordinator=trip_coordinator,
    )

    _schedule_car_refresh(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _register_services(hass)
    return True


def _schedule_car_refresh(
    hass: HomeAssistant, entry: MyHondaPlusConfigEntry,
) -> None:
    """Schedule a recurring refresh-from-car if configured."""
    interval = entry.data.get(CONF_CAR_REFRESH_INTERVAL, DEFAULT_CAR_REFRESH_INTERVAL)
    if not interval or interval <= 0:
        return

    coordinator = entry.runtime_data.coordinator

    @callback
    def _do_car_refresh(_now) -> None:
        """Refresh from car and reschedule."""
        async def _refresh():
            if entry.runtime_data.car_refresh_enabled:
                try:
                    await coordinator.async_refresh_from_car()
                    LOGGER.debug("Scheduled refresh from car completed")
                except Exception:
                    LOGGER.warning("Scheduled refresh from car failed", exc_info=True)
            entry.runtime_data.car_refresh_unsub = async_call_later(
                hass, interval, _do_car_refresh,
            )

        hass.async_create_task(_refresh())

    entry.runtime_data.car_refresh_unsub = async_call_later(
        hass, interval, _do_car_refresh,
    )


def _get_coordinator(hass: HomeAssistant) -> HondaDataUpdateCoordinator:
    """Get the first available coordinator."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if hasattr(entry, "runtime_data") and entry.runtime_data:
            return entry.runtime_data.coordinator
    raise ValueError("No My Honda+ config entry found")


def _register_services(hass: HomeAssistant) -> None:
    """Register integration services (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_CHARGE_SCHEDULE):
        return

    def _optimistic_schedule_update(
        coordinator: HondaDataUpdateCoordinator,
        key: str,
        rules: list[dict],
    ) -> None:
        """Optimistically update schedule data and schedule a delayed refresh."""
        enriched = []
        for r in rules:
            rule = dict(r)
            rule.setdefault("enabled", True)
            days = rule.get("days", "")
            if isinstance(days, str):
                rule["days"] = [d.strip() for d in days.split(",") if d.strip()]
            enriched.append(rule)
        data = dict(coordinator.data)
        data[key] = enriched
        coordinator.async_set_updated_data(data)

        @callback
        def _refresh(_now):
            hass.async_create_task(coordinator.async_request_refresh())

        async_call_later(hass, 30, _refresh)

    async def handle_set_charge_schedule(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        rules = call.data["rules"]
        await coordinator.async_send_command(
            coordinator.api.set_charge_schedule, coordinator.vin, rules,
        )
        _optimistic_schedule_update(coordinator, "charge_schedule", rules)

    async def handle_set_climate_schedule(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        rules = call.data["rules"]
        await coordinator.async_send_command(
            coordinator.api.set_climate_schedule, coordinator.vin, rules,
        )
        _optimistic_schedule_update(coordinator, "climate_schedule", rules)

    async def handle_climate_on(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        temp = call.data.get("temp", "normal")
        duration = call.data.get("duration", 30)
        defrost = call.data.get("defrost", True)
        await coordinator.async_send_command_and_wait(
            coordinator.api.set_climate_settings,
            coordinator.vin, temp, duration, defrost,
        )
        confirmed = await coordinator.async_send_command_and_wait(
            coordinator.api.remote_climate_start, coordinator.vin,
        )
        if confirmed:
            new_data = dict(coordinator.data)
            new_data["climate_active"] = True
            new_data["climate_temp"] = temp
            new_data["climate_duration"] = duration
            new_data["climate_defrost"] = defrost
            coordinator.async_set_updated_data(new_data)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_CHARGE_SCHEDULE,
        handle_set_charge_schedule, schema=SERVICE_CHARGE_SCHEDULE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_CLIMATE_SCHEDULE,
        handle_set_climate_schedule, schema=SERVICE_CLIMATE_SCHEDULE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CLIMATE_ON,
        handle_climate_on, schema=SERVICE_CLIMATE_ON_SCHEMA,
    )


async def async_unload_entry(hass: HomeAssistant, entry: MyHondaPlusConfigEntry) -> bool:
    """Unload a config entry."""
    if entry.runtime_data.car_refresh_unsub:
        entry.runtime_data.car_refresh_unsub()
        entry.runtime_data.car_refresh_unsub = None
    result = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if result and not hass.config_entries.async_entries(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_SET_CHARGE_SCHEDULE)
        hass.services.async_remove(DOMAIN, SERVICE_SET_CLIMATE_SCHEDULE)
        hass.services.async_remove(DOMAIN, SERVICE_CLIMATE_ON)
    return result


async def async_reload_entry(hass: HomeAssistant, entry: MyHondaPlusConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
