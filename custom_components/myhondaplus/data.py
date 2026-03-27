"""Custom types for My Honda+ integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE

if TYPE_CHECKING:
    from .coordinator import HondaDataUpdateCoordinator, HondaTripCoordinator

type MyHondaPlusConfigEntry = ConfigEntry[MyHondaPlusData]


@dataclass
class MyHondaPlusData:
    """Data for the My Honda+ integration."""

    coordinator: HondaDataUpdateCoordinator
    trip_coordinator: HondaTripCoordinator
    car_refresh_unsub: CALLBACK_TYPE | None = field(default=None)
    car_refresh_enabled: bool = field(default=True)
