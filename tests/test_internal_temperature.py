"""Tests for Honda's hint to hide the internal temperature (issue #79)."""

from types import SimpleNamespace

import pytest
from pymyhondaplus.api import UIConfiguration, VehicleCapabilities

from custom_components.myhondaplus.sensor import SENSOR_DESCRIPTIONS, _sensor_enabled

CABIN = next(d for d in SENSOR_DESCRIPTIONS if d.key == "cabin_temp")
INTERIOR = next(d for d in SENSOR_DESCRIPTIONS if d.key == "interior_temp")


def _vehicle(fuel_type: str, hide: bool) -> SimpleNamespace:
    return SimpleNamespace(
        fuel_type=fuel_type,
        ui_config=UIConfiguration(hide_internal_temperature=hide),
        capabilities=VehicleCapabilities(),
    )


@pytest.mark.parametrize("fuel_type", ["E", "X", "G"])
@pytest.mark.parametrize("hide", [False, True])
def test_hint_hides_cabin_temperature(fuel_type, hide):
    """The app hides the cabin temperature, so Home Assistant does too."""
    assert _sensor_enabled(CABIN, _vehicle(fuel_type, hide)) is not hide


@pytest.mark.parametrize("fuel_type", ["E", "X", "G"])
@pytest.mark.parametrize("hide", [False, True])
def test_hint_leaves_interior_temperature(fuel_type, hide):
    """Interior temperature only follows the fuel type."""
    assert _sensor_enabled(INTERIOR, _vehicle(fuel_type, hide)) is (
        fuel_type in {"E", "X"}
    )
