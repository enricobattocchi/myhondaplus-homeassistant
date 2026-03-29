"""Diagnostics support for My Honda+."""

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_KEY_PEM,
    CONF_PERSONAL_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_ID,
)
from .data import MyHondaPlusConfigEntry

TO_REDACT = {
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_DEVICE_KEY_PEM,
    CONF_PERSONAL_ID,
    CONF_USER_ID,
    "email",
    "password",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: MyHondaPlusConfigEntry,
) -> dict:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator
    trip_coordinator = entry.runtime_data.trip_coordinator
    return {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "coordinator_data": coordinator.data,
        "trip_data": trip_coordinator.data,
    }
