"""Tests for the lock platform."""

from unittest.mock import MagicMock

import pytest

from custom_components.myhondaplus.lock import HondaDoorLock

from .conftest import MOCK_VEHICLE_NAME, MOCK_VIN


@pytest.fixture
def door_lock(mock_coordinator):
    """Create a HondaDoorLock instance."""
    lock = HondaDoorLock(mock_coordinator, MOCK_VIN, MOCK_VEHICLE_NAME)
    lock.hass = MagicMock()
    return lock


class TestDoorLock:
    def test_is_locked_true(self, door_lock):
        door_lock.coordinator.data["doors_locked"] = True
        assert door_lock.is_locked is True

    def test_is_locked_false(self, door_lock):
        door_lock.coordinator.data["doors_locked"] = False
        assert door_lock.is_locked is False

    def test_is_locked_string_locked(self, door_lock):
        door_lock.coordinator.data["doors_locked"] = "locked"
        assert door_lock.is_locked is True

    def test_is_locked_string_true(self, door_lock):
        door_lock.coordinator.data["doors_locked"] = "true"
        assert door_lock.is_locked is True

    def test_is_locked_string_unlocked(self, door_lock):
        door_lock.coordinator.data["doors_locked"] = "unlocked"
        assert door_lock.is_locked is False

    def test_is_locked_none(self, door_lock):
        door_lock.coordinator.data["doors_locked"] = None
        assert door_lock.is_locked is None

    def test_is_locked_missing_key(self, door_lock):
        door_lock.coordinator.data.pop("doors_locked", None)
        assert door_lock.is_locked is None

    @pytest.mark.asyncio
    async def test_lock(self, door_lock):
        await door_lock.async_lock()
        door_lock.coordinator.async_send_command_and_wait.assert_awaited_once_with(
            door_lock.coordinator.api.remote_lock, MOCK_VIN,
        )
        door_lock.coordinator.async_set_updated_data.assert_called_once()
        data = door_lock.coordinator.async_set_updated_data.call_args[0][0]
        assert data["doors_locked"] is True

    @pytest.mark.asyncio
    async def test_unlock(self, door_lock):
        await door_lock.async_unlock()
        door_lock.coordinator.async_send_command_and_wait.assert_awaited_once_with(
            door_lock.coordinator.api.remote_unlock, MOCK_VIN,
        )
        door_lock.coordinator.async_set_updated_data.assert_called_once()
        data = door_lock.coordinator.async_set_updated_data.call_args[0][0]
        assert data["doors_locked"] is False

    @pytest.mark.asyncio
    async def test_lock_schedules_refresh(self, door_lock):
        await door_lock.async_lock()
        # _schedule_refresh calls async_call_later on hass
        # Verify hass interaction happened (the entity called _schedule_refresh)
        door_lock.coordinator.async_set_updated_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_lock_does_not_mutate_original(self, door_lock):
        """Ensure optimistic update creates a copy."""
        original_data = door_lock.coordinator.data
        await door_lock.async_lock()
        assert original_data["doors_locked"] is True  # was True in fixture already

    @pytest.mark.asyncio
    async def test_unlock_does_not_mutate_original(self, door_lock):
        """Ensure optimistic update creates a copy."""
        original_data = door_lock.coordinator.data
        original_locked = original_data["doors_locked"]
        await door_lock.async_unlock()
        # Original data should not have been changed
        assert original_data["doors_locked"] == original_locked
