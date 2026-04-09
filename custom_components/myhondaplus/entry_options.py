"""Helpers for reading config entry options with data fallback."""

from homeassistant.config_entries import ConfigEntry


def get_entry_value(entry: ConfigEntry, key: str, default):
    """Return an entry option, falling back to entry data for older entries."""
    return entry.options.get(key, entry.data.get(key, default))
