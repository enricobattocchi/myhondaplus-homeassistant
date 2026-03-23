"""Custom types for My Honda+ integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import HondaDataUpdateCoordinator, HondaTripCoordinator

type MyHondaPlusConfigEntry = ConfigEntry[MyHondaPlusData]


@dataclass
class MyHondaPlusData:
    """Data for the My Honda+ integration."""

    coordinator: HondaDataUpdateCoordinator
    trip_coordinator: HondaTripCoordinator
