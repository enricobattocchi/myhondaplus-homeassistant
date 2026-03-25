"""My Honda+ integration for Home Assistant."""

import voluptuous as vol
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN
from .coordinator import HondaDataUpdateCoordinator, HondaTripCoordinator
from .data import MyHondaPlusConfigEntry, MyHondaPlusData

PLATFORMS = [Platform.SENSOR, Platform.BUTTON, Platform.NUMBER, Platform.SWITCH, Platform.LOCK]

SERVICE_SET_CHARGE_SCHEDULE = "set_charge_schedule"
SERVICE_SET_CLIMATE_SCHEDULE = "set_climate_schedule"

SCHEDULE_RULE_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)
SERVICE_SCHEDULE_SCHEMA = vol.Schema({
    vol.Required("rules"): [SCHEDULE_RULE_SCHEMA],
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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _register_services(hass)
    return True


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

    hass.services.async_register(
        DOMAIN, SERVICE_SET_CHARGE_SCHEDULE,
        handle_set_charge_schedule, schema=SERVICE_SCHEDULE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_CLIMATE_SCHEDULE,
        handle_set_climate_schedule, schema=SERVICE_SCHEDULE_SCHEMA,
    )


async def async_unload_entry(hass: HomeAssistant, entry: MyHondaPlusConfigEntry) -> bool:
    """Unload a config entry."""
    result = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if result and not hass.config_entries.async_entries(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_SET_CHARGE_SCHEDULE)
        hass.services.async_remove(DOMAIN, SERVICE_SET_CLIMATE_SCHEDULE)
    return result


async def async_reload_entry(hass: HomeAssistant, entry: MyHondaPlusConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
