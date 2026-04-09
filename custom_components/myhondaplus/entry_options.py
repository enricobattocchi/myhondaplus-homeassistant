"""Helpers for reading config entry options with data fallback."""

from homeassistant.config_entries import ConfigEntry


def get_entry_value(entry: ConfigEntry, key: str, default):
    """Return an entry option."""
    return entry.options.get(key, default)
