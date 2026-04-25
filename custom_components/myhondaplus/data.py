"""Custom types for My Honda+ integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE
from pymyhondaplus.api import UIConfiguration, VehicleCapabilities

if TYPE_CHECKING:
    from pymyhondaplus.api import HondaAPI

    from .coordinator import HondaDataUpdateCoordinator, HondaTripCoordinator

type MyHondaPlusConfigEntry = ConfigEntry[MyHondaPlusData]


def _all_capable() -> VehicleCapabilities:
    """Return capabilities with everything enabled (safe default)."""
    return VehicleCapabilities(
        remote_lock=True,
        remote_climate=True,
        remote_charge=True,
        remote_horn=True,
        digital_key=True,
        charge_schedule=True,
        climate_schedule=True,
        max_charge=True,
        car_finder=True,
        journey_history=True,
        send_poi=True,
        geo_fence=True,
    )


@dataclass
class VehicleData:
    """Data for a single vehicle."""

    coordinator: HondaDataUpdateCoordinator
    trip_coordinator: HondaTripCoordinator | None
    vin: str
    vehicle_name: str = ""
    fuel_type: str = ""
    capabilities: VehicleCapabilities = field(default_factory=_all_capable)
    ui_config: UIConfiguration = field(default_factory=UIConfiguration)
    car_refresh_unsub: CALLBACK_TYPE | None = field(default=None)
    car_refresh_enabled: bool = field(default=True)
    location_refresh_unsub: CALLBACK_TYPE | None = field(default=None)


@dataclass
class MyHondaPlusData:
    """Data for the My Honda+ integration."""

    vehicles: dict[str, VehicleData]
    api: HondaAPI
