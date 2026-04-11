"""Custom types for My Honda+ integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE

if TYPE_CHECKING:
    from pymyhondaplus.api import HondaAPI

    from .coordinator import HondaDataUpdateCoordinator, HondaTripCoordinator

type MyHondaPlusConfigEntry = ConfigEntry[MyHondaPlusData]


@dataclass
class VehicleData:
    """Data for a single vehicle."""

    coordinator: HondaDataUpdateCoordinator
    trip_coordinator: HondaTripCoordinator
    vin: str
    vehicle_name: str = ""
    fuel_type: str = ""
    car_refresh_unsub: CALLBACK_TYPE | None = field(default=None)
    car_refresh_enabled: bool = field(default=True)
    location_refresh_unsub: CALLBACK_TYPE | None = field(default=None)


@dataclass
class MyHondaPlusData:
    """Data for the My Honda+ integration."""

    vehicles: dict[str, VehicleData]
    api: HondaAPI
