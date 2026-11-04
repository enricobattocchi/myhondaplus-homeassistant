"""Diagnostics support for My Honda+."""

from dataclasses import asdict

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_KEY_PEM,
    CONF_PERSONAL_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_ID,
    CONF_VEHICLE_NAME,
    CONF_VIN,
)
from .data import MyHondaPlusConfigEntry

TO_REDACT = {
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_DEVICE_KEY_PEM,
    CONF_PERSONAL_ID,
    CONF_USER_ID,
    CONF_VEHICLE_NAME,
    CONF_VIN,
    "email",
    "latitude",
    "longitude",
    "password",
    "title",
    "unique_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: MyHondaPlusConfigEntry,
) -> dict:
    """Return diagnostics for a config entry."""
    vehicles_diag = {}
    for index, vd in enumerate(entry.runtime_data.vehicles.values(), start=1):
        dashboard = vd.coordinator.data
        vehicles_diag[f"vehicle_{index}"] = {
            # async_redact_data only descends into mappings and lists, so the
            # dashboard dataclass (and its nested geofence) must be converted.
            "coordinator_data": asdict(dashboard) if dashboard is not None else None,
            "trip_data": vd.trip_coordinator.data if vd.trip_coordinator else None,
            "capabilities": vd.capabilities.to_dict(),
            "ui_config": vd.ui_config.to_dict(),
        }
    return async_redact_data(
        {
            "config_entry": entry.as_dict(),
            "vehicles": vehicles_diag,
        },
        TO_REDACT,
    )
