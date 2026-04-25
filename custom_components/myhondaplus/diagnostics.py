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
    vehicles_diag = {}
    for vin, vd in entry.runtime_data.vehicles.items():
        vehicles_diag[vin] = {
            "coordinator_data": vd.coordinator.data,
            "trip_data": vd.trip_coordinator.data if vd.trip_coordinator else None,
            "capabilities": vd.capabilities.to_dict(),
            "ui_config": vd.ui_config.to_dict(),
        }
    return {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "vehicles": vehicles_diag,
    }
