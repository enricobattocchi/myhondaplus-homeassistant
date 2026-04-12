"""My Honda+ integration for Home Assistant."""

import re
from dataclasses import replace

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_EMAIL, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import selector
from homeassistant.helpers.event import async_call_later
from pymyhondaplus.api import HondaAPI, Vehicle

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CAR_REFRESH_INTERVAL,
    CONF_FUEL_TYPE,
    CONF_LOCATION_REFRESH_INTERVAL,
    CONF_MODEL,
    CONF_PERSONAL_ID,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_USER_ID,
    CONF_VEHICLE_NAME,
    CONF_VEHICLES,
    CONF_VIN,
    DEFAULT_CAR_REFRESH_INTERVAL,
    DEFAULT_LOCATION_REFRESH_INTERVAL,
    DOMAIN,
    LOGGER,
)
from .coordinator import HondaDataUpdateCoordinator, HondaTripCoordinator
from .data import MyHondaPlusConfigEntry, MyHondaPlusData, VehicleData
from .entry_options import get_entry_value

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

SERVICE_SET_CHARGE_SCHEDULE = "set_charge_schedule"
SERVICE_SET_CLIMATE_SCHEDULE = "set_climate_schedule"
SERVICE_CLIMATE_ON = "climate_on"
ATTR_DEVICE = "device"


VALID_DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def _validate_days(value: str) -> str:
    """Validate a comma-separated weekday list."""
    if not isinstance(value, str):
        raise vol.Invalid("days must be a comma-separated string")
    days = [day.strip().lower() for day in value.split(",") if day.strip()]
    if not days:
        raise vol.Invalid("at least one day is required")
    if any(day not in VALID_DAYS for day in days):
        raise vol.Invalid("days must only contain mon-sun")
    if len(days) != len(set(days)):
        raise vol.Invalid("days must not contain duplicates")
    return ",".join(days)


def _validate_time(value: str) -> str:
    """Validate a time string in HH:MM format."""
    if not isinstance(value, str):
        raise vol.Invalid("time must be a string")
    if not TIME_PATTERN.match(value):
        raise vol.Invalid("time must be in HH:MM format")
    return value


CHARGE_RULE_SCHEMA = vol.Schema(
    {
        vol.Required("days"): _validate_days,
        vol.Required("location"): vol.In(["home", "all"]),
        vol.Required("start_time"): _validate_time,
        vol.Required("end_time"): _validate_time,
        vol.Optional("enabled", default=True): bool,
    }
)

CLIMATE_RULE_SCHEMA = vol.Schema(
    {
        vol.Required("days"): _validate_days,
        vol.Required("start_time"): _validate_time,
        vol.Optional("enabled", default=True): bool,
    }
)

BASE_SERVICE_FIELDS = {
    vol.Required(ATTR_DEVICE): selector.DeviceSelector(
        {
            "integration": DOMAIN,
        }
    ),
}
SERVICE_CLIMATE_ON_FIELDS = {
    **BASE_SERVICE_FIELDS,
    vol.Optional("temp", default="normal"): vol.In(["cooler", "normal", "hotter"]),
    vol.Optional("duration", default=30): vol.All(
        vol.Coerce(int), vol.In([10, 20, 30])
    ),
    vol.Optional("defrost", default=True): bool,
}
SERVICE_CHARGE_SCHEDULE_FIELDS = {
    **BASE_SERVICE_FIELDS,
    vol.Required("rules"): vol.All([CHARGE_RULE_SCHEMA], vol.Length(max=2)),
}
SERVICE_CLIMATE_SCHEDULE_FIELDS = {
    **BASE_SERVICE_FIELDS,
    vol.Required("rules"): vol.All([CLIMATE_RULE_SCHEMA], vol.Length(max=7)),
}

SERVICE_CLIMATE_ON_SCHEMA = vol.Schema(SERVICE_CLIMATE_ON_FIELDS)
SERVICE_CHARGE_SCHEDULE_SCHEMA = vol.Schema(SERVICE_CHARGE_SCHEDULE_FIELDS)
SERVICE_CLIMATE_SCHEDULE_SCHEMA = vol.Schema(SERVICE_CLIMATE_SCHEDULE_FIELDS)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the My Honda+ integration."""
    _register_services(hass)
    return True


async def async_migrate_entry(
    hass: HomeAssistant, entry: MyHondaPlusConfigEntry
) -> bool:
    """Migrate old config entries to the latest version."""
    if entry.version == 1:
        option_keys = (
            CONF_SCAN_INTERVAL,
            CONF_CAR_REFRESH_INTERVAL,
            CONF_LOCATION_REFRESH_INTERVAL,
        )
        new_data = dict(entry.data)
        new_options = dict(entry.options)

        for key in option_keys:
            if key in new_data:
                value = new_data.pop(key)
                if key not in new_options:
                    new_options[key] = value

        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            options=new_options,
            version=2,
        )

    if entry.version == 2:
        new_data = dict(entry.data)
        vehicles = [
            {
                CONF_VIN: new_data.pop(CONF_VIN),
                CONF_VEHICLE_NAME: new_data.pop(CONF_VEHICLE_NAME, ""),
                CONF_FUEL_TYPE: new_data.pop(CONF_FUEL_TYPE, ""),
            }
        ]
        new_data[CONF_VEHICLES] = vehicles

        email = new_data.get(CONF_EMAIL, "")
        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            unique_id=email.lower() if email else entry.unique_id,
            version=3,
        )

    return True


def _consolidate_duplicate_entries(
    hass: HomeAssistant,
    entry: MyHondaPlusConfigEntry,
) -> None:
    """Merge duplicate v3 entries for the same email into this entry.

    Phase 2 of migration: runs at the start of async_setup_entry.
    """
    email = entry.data.get(CONF_EMAIL, "").lower()
    if not email:
        return

    duplicates = []
    for other in hass.config_entries.async_entries(DOMAIN):
        if other.entry_id == entry.entry_id:
            continue
        if other.data.get(CONF_EMAIL, "").lower() == email:
            duplicates.append(other)

    if not duplicates:
        return

    # Merge vehicles from duplicates into this entry
    existing_vins = {v[CONF_VIN] for v in entry.data.get(CONF_VEHICLES, [])}
    merged_vehicles = list(entry.data.get(CONF_VEHICLES, []))

    for dup in duplicates:
        for v in dup.data.get(CONF_VEHICLES, []):
            if v[CONF_VIN] not in existing_vins:
                merged_vehicles.append(v)
                existing_vins.add(v[CONF_VIN])

    new_data = {**entry.data, CONF_VEHICLES: merged_vehicles}
    hass.config_entries.async_update_entry(entry, data=new_data)

    for dup in duplicates:
        LOGGER.info(
            "Removing duplicate config entry %s (merged into %s)",
            dup.entry_id,
            entry.entry_id,
        )
        hass.async_create_task(hass.config_entries.async_remove(dup.entry_id))


def _cleanup_removed_vehicles(
    hass: HomeAssistant,
    entry: MyHondaPlusConfigEntry,
    active_vins: set[str],
) -> None:
    """Remove devices/entities for vehicles no longer in the vehicle list."""
    device_registry = dr.async_get(hass)
    devices_to_remove = []
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        for domain, identifier in device.identifiers:
            if domain == DOMAIN and identifier not in active_vins:
                devices_to_remove.append(device.id)
                break

    for device_id in devices_to_remove:
        LOGGER.info("Removing device for vehicle no longer in account: %s", device_id)
        device_registry.async_remove_device(device_id)


async def async_setup_entry(hass: HomeAssistant, entry: MyHondaPlusConfigEntry) -> bool:
    """Set up My Honda+ from a config entry."""
    # Phase 2: consolidate duplicate entries from migration
    _consolidate_duplicate_entries(hass, entry)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Create one shared API instance
    api = HondaAPI()
    api.set_tokens(
        access_token=entry.data[CONF_ACCESS_TOKEN],
        refresh_token=entry.data[CONF_REFRESH_TOKEN],
        personal_id=entry.data.get(CONF_PERSONAL_ID, ""),
        user_id=entry.data.get(CONF_USER_ID, ""),
    )

    # Fetch vehicle metadata (capabilities, UI config, backfill models)
    api_vehicles = await _fetch_vehicle_metadata(hass, entry, api)

    vehicles: dict[str, VehicleData] = {}
    for v in entry.data.get(CONF_VEHICLES, []):
        vin = v[CONF_VIN]
        vehicle_name = v.get(CONF_VEHICLE_NAME, "")
        fuel_type = v.get(CONF_FUEL_TYPE, "")

        coordinator = HondaDataUpdateCoordinator(
            hass,
            entry,
            api,
            vin,
            vehicle_name,
        )
        await coordinator.async_config_entry_first_refresh()

        trip_coordinator = HondaTripCoordinator(
            hass,
            entry,
            api,
            coordinator._persist_tokens_if_changed,
            vin=vin,
            fuel_type=fuel_type,
            main_coordinator=coordinator,
        )
        await trip_coordinator.async_config_entry_first_refresh()

        api_vehicle = api_vehicles.get(vin)
        vehicles[vin] = VehicleData(
            coordinator=coordinator,
            trip_coordinator=trip_coordinator,
            vin=vin,
            vehicle_name=vehicle_name,
            fuel_type=fuel_type,
            **(
                {
                    "capabilities": api_vehicle.capabilities,
                    "ui_config": api_vehicle.ui_config,
                }
                if api_vehicle
                else {}
            ),
        )

    entry.runtime_data = MyHondaPlusData(vehicles=vehicles, api=api)

    # Clean up devices for removed vehicles
    _cleanup_removed_vehicles(hass, entry, set(vehicles.keys()))

    # Schedule per-vehicle refreshes
    for vd in vehicles.values():
        _schedule_car_refresh(hass, entry, vd)
        _schedule_location_refresh(hass, entry, vd)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set model on devices from stored vehicle data
    _update_device_models(hass, entry)

    return True


async def _fetch_vehicle_metadata(
    hass: HomeAssistant,
    entry: MyHondaPlusConfigEntry,
    api: HondaAPI,
) -> dict[str, Vehicle]:
    """Fetch Vehicle objects from the API.

    Also backfills model names for vehicles that don't have them (upgrade path).
    Returns a dict of VIN → Vehicle for capability/UI config extraction.
    """
    try:
        api_vehicles = await hass.async_add_executor_job(api.get_vehicles)
    except Exception:
        LOGGER.debug("Could not fetch vehicle metadata", exc_info=True)
        return {}

    vehicles_by_vin = {v.vin: v for v in api_vehicles}

    # Backfill model names if missing
    vehicle_list = entry.data.get(CONF_VEHICLES, [])
    if not all(v.get(CONF_MODEL) for v in vehicle_list):
        updated = []
        for v in vehicle_list:
            vin = v[CONF_VIN]
            api_v = vehicles_by_vin.get(vin)
            if api_v and not v.get(CONF_MODEL):
                model = _build_model_name_from_vehicle(api_v)
                updated.append({**v, CONF_MODEL: model})
            else:
                updated.append(v)
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_VEHICLES: updated},
        )

    return vehicles_by_vin


def _build_model_name_from_vehicle(vehicle: Vehicle) -> str:
    """Build a display model name from a Vehicle dataclass."""
    friendly = vehicle.model_name
    grade = vehicle.grade
    year = vehicle.model_year

    if friendly and grade:
        parts = grade.split(None, 1)
        grade = (
            parts[1].title() if len(parts) > 1 and len(parts[0]) <= 2 else grade.title()
        )

    name = friendly
    if grade:
        name = f"{name} {grade}" if name else grade
    if year:
        name = f"{name} ({year})" if name else str(year)
    return name


def _update_device_models(
    hass: HomeAssistant,
    entry: MyHondaPlusConfigEntry,
) -> None:
    """Set the model field on devices from stored vehicle data."""
    device_registry = dr.async_get(hass)
    for v in entry.data.get(CONF_VEHICLES, []):
        model = v.get(CONF_MODEL, "")
        if not model:
            continue
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, v[CONF_VIN])},
        )
        if device and device.model != model:
            device_registry.async_update_device(device.id, model=model)


def _schedule_car_refresh(
    hass: HomeAssistant,
    entry: MyHondaPlusConfigEntry,
    vd: VehicleData,
) -> None:
    """Schedule a recurring refresh-from-car if configured."""
    interval = get_entry_value(
        entry,
        CONF_CAR_REFRESH_INTERVAL,
        DEFAULT_CAR_REFRESH_INTERVAL,
    )
    if not interval or interval <= 0:
        return

    coordinator = vd.coordinator

    @callback
    def _do_car_refresh(_now) -> None:
        """Refresh from car and reschedule."""

        async def _refresh():
            if vd.car_refresh_enabled:
                try:
                    await coordinator.async_refresh_from_car(
                        notify_on_timeout=False,
                    )
                    LOGGER.debug("Scheduled refresh from car completed for %s", vd.vin)
                except Exception:
                    LOGGER.warning(
                        "Scheduled refresh from car failed for %s",
                        vd.vin,
                        exc_info=True,
                    )
            vd.car_refresh_unsub = async_call_later(
                hass,
                interval,
                _do_car_refresh,
            )

        hass.async_create_task(_refresh())

    vd.car_refresh_unsub = async_call_later(
        hass,
        interval,
        _do_car_refresh,
    )


def _schedule_location_refresh(
    hass: HomeAssistant,
    entry: MyHondaPlusConfigEntry,
    vd: VehicleData,
) -> None:
    """Schedule a recurring location refresh if configured."""
    interval = get_entry_value(
        entry,
        CONF_LOCATION_REFRESH_INTERVAL,
        DEFAULT_LOCATION_REFRESH_INTERVAL,
    )
    if not interval or interval <= 0:
        return

    coordinator = vd.coordinator

    @callback
    def _do_location_refresh(_now) -> None:
        """Refresh location and reschedule."""

        async def _refresh():
            try:
                await coordinator.async_refresh_location(
                    notify_on_timeout=False,
                )
                LOGGER.debug("Scheduled location refresh completed for %s", vd.vin)
            except Exception:
                LOGGER.warning(
                    "Scheduled location refresh failed for %s", vd.vin, exc_info=True
                )
            vd.location_refresh_unsub = async_call_later(
                hass,
                interval,
                _do_location_refresh,
            )

        hass.async_create_task(_refresh())

    vd.location_refresh_unsub = async_call_later(
        hass,
        interval,
        _do_location_refresh,
    )


def _get_coordinator(
    hass: HomeAssistant,
    call: ServiceCall,
) -> HondaDataUpdateCoordinator:
    """Resolve the coordinator for a service call via device selector."""
    device_id = call.data.get(ATTR_DEVICE)
    if not device_id:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_required",
        )

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if device is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
        )

    # Extract VIN from device identifiers: {(DOMAIN, vin)}
    vin = None
    for domain, identifier in device.identifiers:
        if domain == DOMAIN:
            vin = identifier
            break
    if vin is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
        )

    # Find the config entry that owns this vehicle
    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if (
            entry
            and entry.domain == DOMAIN
            and entry.state == ConfigEntryState.LOADED
            and hasattr(entry, "runtime_data")
            and entry.runtime_data
        ):
            vehicle = entry.runtime_data.vehicles.get(vin)
            if vehicle:
                return vehicle.coordinator

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="device_not_found",
    )


def _register_services(hass: HomeAssistant) -> None:
    """Register integration services (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_CHARGE_SCHEDULE):
        return

    def _optimistic_schedule_update(
        coordinator: HondaDataUpdateCoordinator,
        key: str,
        rules: list[dict],
    ) -> None:
        """Optimistically update schedule data and schedule a delayed refresh."""
        enriched = []
        for r in rules:
            rule = dict(r)
            rule.setdefault("enabled", True)
            days = rule.get("days", "")
            if isinstance(days, str):
                rule["days"] = [d.strip() for d in days.split(",") if d.strip()]
            enriched.append(rule)
        coordinator.async_set_updated_data(
            replace(coordinator.data, **{key: enriched})
        )

        @callback
        def _refresh(_now):
            hass.async_create_task(coordinator.async_request_refresh())

        async_call_later(hass, 30, _refresh)

    async def handle_set_charge_schedule(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, call)
        rules = call.data["rules"]
        await coordinator.async_send_command(
            coordinator.api.set_charge_schedule,
            coordinator.vin,
            rules,
        )
        _optimistic_schedule_update(coordinator, "charge_schedule", rules)

    async def handle_set_climate_schedule(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, call)
        rules = call.data["rules"]
        await coordinator.async_send_command(
            coordinator.api.set_climate_schedule,
            coordinator.vin,
            rules,
        )
        _optimistic_schedule_update(coordinator, "climate_schedule", rules)

    async def handle_climate_on(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, call)
        temp = call.data.get("temp", "normal")
        duration = call.data.get("duration", 30)
        defrost = call.data.get("defrost", True)
        await coordinator.async_send_command_and_wait(
            coordinator.api.set_climate_settings,
            coordinator.vin,
            temp,
            duration,
            defrost,
        )
        confirmed = await coordinator.async_send_command_and_wait(
            coordinator.api.remote_climate_start,
            coordinator.vin,
        )
        if confirmed:
            coordinator.async_set_updated_data(
                replace(
                    coordinator.data,
                    climate_active=True,
                    climate_temp=temp,
                    climate_duration=duration,
                    climate_defrost=defrost,
                )
            )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CHARGE_SCHEDULE,
        handle_set_charge_schedule,
        schema=SERVICE_CHARGE_SCHEDULE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CLIMATE_SCHEDULE,
        handle_set_climate_schedule,
        schema=SERVICE_CLIMATE_SCHEDULE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLIMATE_ON,
        handle_climate_on,
        schema=SERVICE_CLIMATE_ON_SCHEMA,
    )


async def async_unload_entry(
    hass: HomeAssistant, entry: MyHondaPlusConfigEntry
) -> bool:
    """Unload a config entry."""
    for vd in entry.runtime_data.vehicles.values():
        if vd.car_refresh_unsub:
            vd.car_refresh_unsub()
            vd.car_refresh_unsub = None
        if vd.location_refresh_unsub:
            vd.location_refresh_unsub()
            vd.location_refresh_unsub = None
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant, entry: MyHondaPlusConfigEntry
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
