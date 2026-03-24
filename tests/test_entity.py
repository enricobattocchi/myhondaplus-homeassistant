"""Tests for the base entity class."""

from unittest.mock import MagicMock

from custom_components.myhondaplus.entity import FUEL_TYPE_LABELS, MyHondaPlusEntity

from .conftest import MOCK_VEHICLE_NAME, MOCK_VIN


def make_entity(coordinator, vin=MOCK_VIN, vehicle_name=MOCK_VEHICLE_NAME):
    """Create a MyHondaPlusEntity instance."""
    desc = MagicMock()
    desc.key = "test_key"
    entity = MyHondaPlusEntity(coordinator, desc, vin, vehicle_name)
    entity.hass = MagicMock()
    return entity


class TestMyHondaPlusEntity:
    def test_unique_id(self, mock_coordinator):
        entity = make_entity(mock_coordinator)
        assert entity.unique_id == f"{MOCK_VIN}_test_key"

    def test_device_info_with_name(self, mock_coordinator):
        entity = make_entity(mock_coordinator)
        info = entity.device_info
        assert info["name"] == MOCK_VEHICLE_NAME
        assert ("myhondaplus", MOCK_VIN) in info["identifiers"]
        assert info["manufacturer"] == "Honda"

    def test_device_info_without_name(self, mock_coordinator):
        entity = make_entity(mock_coordinator, vehicle_name="")
        info = entity.device_info
        assert info["name"] == f"Honda {MOCK_VIN[-6:]}"

    def test_device_info_model_electric(self, mock_coordinator):
        entity = make_entity(mock_coordinator)
        info = entity.device_info
        assert info["model"] == "Electric"

    def test_device_info_model_no_fuel_type(self, mock_coordinator):
        mock_coordinator.entry.data["fuel_type"] = ""
        entity = make_entity(mock_coordinator)
        info = entity.device_info
        assert "model" not in info

    def test_fuel_type_labels(self):
        assert FUEL_TYPE_LABELS["E"] == "Electric"
        assert FUEL_TYPE_LABELS["H"] == "Hybrid"
        assert FUEL_TYPE_LABELS["G"] == "Gasoline"
        assert FUEL_TYPE_LABELS["D"] == "Diesel"

    def test_has_entity_name(self, mock_coordinator):
        entity = make_entity(mock_coordinator)
        assert entity._attr_has_entity_name is True
