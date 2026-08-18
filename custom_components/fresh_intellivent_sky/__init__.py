"""The Fresh Intellivent Sky integration."""
from __future__ import annotations

import asyncio
import logging
from copy import deepcopy
from datetime import datetime, time as dt_time, timedelta

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    AIRING_MODE_UPDATE,
    BOOST_UPDATE,
    CONF_AUTH_KEY,
    CONSTANT_SPEED_UPDATE,
    DOMAIN,
    ENABLED_KEY,
    END_TIME_KEY,
    HUMIDITY_MODE_UPDATE,
    LIGHT_AND_VOC_MODE_UPDATE,
    MAX_RPM_KEY,
    MINUTES_KEY,
    NIGHT_MODE,
    PAUSE_UPDATE,
    RPM_KEY,
    SILENT_HOURS,
    START_TIME_KEY,
    TIMEOUT,
    TIMER_MODE_UPDATE,
    VOC_MODE_UPDATE,
)
from .fetch_and_update import FetchAndUpdate
from .fresh_intellivent import FreshIntelliVent

ALL_UPDATES = [
    BOOST_UPDATE,
    PAUSE_UPDATE,
    CONSTANT_SPEED_UPDATE,
    AIRING_MODE_UPDATE,
    HUMIDITY_MODE_UPDATE,
    LIGHT_AND_VOC_MODE_UPDATE,
    TIMER_MODE_UPDATE,
    VOC_MODE_UPDATE,
]

AUTHENTICATED_PLATFORMS = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]

READ_ONLY_PLATFORMS = [
    Platform.SENSOR,
]

DEFAULT_POLL_INTERVAL = 30
KEEP_CONNECTION_INTERVAL = 1
POLL_INTERVAL_OPTION = "poll_interval"
KEEP_CONNECTION_OPTION = "keep_connection"
DEBUG_LOGGING_OPTION = "debug_logging"
SCHEDULE_STORAGE_VERSION = 1
SCHEDULE_CHECK_INTERVAL = 15

_LOGGER = logging.getLogger(__name__)
_DEBUG_LOGGER = logging.getLogger(f"{__name__}.device_debug")


def _refresh_debug_logger_level(
    hass: HomeAssistant,
    current_coordinator=None,
) -> None:
    """Enable the dedicated debug logger while any SKY has debug enabled."""
    devices = hass.data.get(DOMAIN, {}).get("devices", {})
    enabled = bool(
        getattr(current_coordinator, "debug_logging", False)
    ) or any(
        getattr(device_coordinator, "debug_logging", False)
        for device_coordinator in devices.values()
    )
    _DEBUG_LOGGER.setLevel(logging.DEBUG if enabled else logging.WARNING)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up Fresh Intellivent Sky."""
    hass.data.setdefault(
        DOMAIN,
        {
            "devices": {},
        },
    )
    address = entry.unique_id

    assert address is not None

    ble_device = bluetooth.async_ble_device_from_address(hass, address)

    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Fresh Intellivent Sky device with address {address}"
        )

    auth_key = entry.data.get(CONF_AUTH_KEY)
    initial_poll_interval = int(
        entry.options.get(POLL_INTERVAL_OPTION, DEFAULT_POLL_INTERVAL)
    )
    initial_keep_connection = bool(
        entry.options.get(KEEP_CONNECTION_OPTION, False)
    )
    initial_debug_logging = bool(
        entry.options.get(DEBUG_LOGGING_OPTION, False)
    )
    initial_update_interval = (
        KEEP_CONNECTION_INTERVAL
        if initial_keep_connection
        else initial_poll_interval
    )
    client = FreshIntelliVent(ble_device=ble_device)
    update_lock = asyncio.Lock()
    scheduled_mode_lock = asyncio.Lock()
    schedule_store = Store(
        hass,
        SCHEDULE_STORAGE_VERSION,
        f"{DOMAIN}.{entry.entry_id}.scheduled_modes",
    )

    stored_schedule = await schedule_store.async_load() or {}

    stored_modes = stored_schedule.get("modes", {})
    if not isinstance(stored_modes, dict):
        stored_modes = {}

    def _mode_from_storage(
        mode: str,
        default_start: dt_time,
        default_end: dt_time,
        default_rpm: int,
    ) -> dict:
        """Build one scheduled mode from stored values and defaults."""
        stored_mode = stored_modes.get(mode, {})
        if not isinstance(stored_mode, dict):
            stored_mode = {}

        start_value = stored_mode.get(START_TIME_KEY)
        end_value = stored_mode.get(END_TIME_KEY)

        try:
            start_time = dt_time.fromisoformat(start_value)
        except (TypeError, ValueError):
            start_time = default_start

        try:
            end_time = dt_time.fromisoformat(end_value)
        except (TypeError, ValueError):
            end_time = default_end

        try:
            max_rpm = int(stored_mode.get(MAX_RPM_KEY, default_rpm))
        except (TypeError, ValueError):
            max_rpm = default_rpm

        return {
            "enabled": bool(stored_mode.get("enabled", False)),
            "active": bool(stored_mode.get("active", False)),
            START_TIME_KEY: start_time,
            END_TIME_KEY: end_time,
            MAX_RPM_KEY: min(2400, max(850, max_rpm)),
        }

    device_information_loaded = False
    
    def _set_connection_status(status: str) -> None:
        """Update and immediately publish the BLE connection status."""
        if getattr(coordinator, "connection_status", None) == status:
            return

        coordinator.connection_status = status
        coordinator.async_update_listeners()    

    async def _connect_and_authenticate(
        *,
        reset_device_information: bool = False,
    ) -> None:
        """Connect and authenticate when the BLE link is not active."""
        nonlocal device_information_loaded

        current_ble_device = bluetooth.async_ble_device_from_address(hass, address)

        if not current_ble_device:
            raise UpdateFailed(f"Unable to find device: {address}")

        client.update_ble_device(current_ble_device)

        if reset_device_information:
            device_information_loaded = False

        if client.is_connected:
            _set_connection_status("connected")
            return

        _set_connection_status("connecting")

        try:
            await client.connect(timeout=TIMEOUT)
        except Exception:
            _set_connection_status("disconnected")
            raise

        _set_connection_status("connected")

        if auth_key is not None:
            await client.authenticate(authentication_code=auth_key)

        if not device_information_loaded:
            await client.fetch_device_information()
            device_information_loaded = True
            coordinator.hw_version = client.hw_version
            coordinator.sw_version = client.sw_version
            sw = (client.sw_version or "").strip()
            try:
                sw_version = float(sw)
                coordinator.old_software_version = sw_version < 1.02
            except ValueError:
                coordinator.old_software_version = False
                _LOGGER.warning("Could not parse software version: %s", sw)

    async def _run_update() -> FreshIntelliVent:
        """Fetch live data, apply pending writes, and refresh settings."""
        pending_write = any(
            coordinator.pending_updates.get(update) is not None
            for update in ALL_UPDATES
        )

        if pending_write:
            coordinator.settings_refresh_needed = True

        await _connect_and_authenticate()
        await client.fetch_sensor_data()
        
        service_info = bluetooth.async_last_service_info(
            hass,
            address,
            connectable=True,
        )

        if service_info is not None:
            coordinator.rssi = service_info.rssi
            coordinator.bluetooth_source = service_info.source        

        if coordinator.debug_logging:
            sensors = client.sensors
            _DEBUG_LOGGER.debug(
                "SKY DEBUG "
                "hw_version=%s "
                "fw_version=%s "
                "ble_address=%s "
                "rssi=%s "
                "bluetooth_source=%s "                
                "raw_ble_payload=%s "
                "flags=%s "
                "active_trigger=%s "
                "motor_speed=%s "
                "humidity_raw=%s "
                "odour_raw=%s "
                "light_raw=%s "
                "fan_speed=%s "
                "reference=%s "
                "min_active=%s "
                "temperature=%s "
                "error=%s",
                coordinator.hw_version,
                coordinator.sw_version,
                coordinator.ble_address,
                coordinator.rssi,
                coordinator.bluetooth_source,                
                sensors.raw_ble_payload,
                sensors.flags,
                sensors.active_trigger,
                sensors.motor_speed,
                sensors.humidity_raw,
                sensors.voc_raw,
                sensors.light_raw,
                sensors.rpm,
                sensors.reference_raw,
                sensors.minimum_active,
                sensors.temperature,
                sensors.error,
            )

        await client.fetch_pause()

        settings_refresh_needed = (
            not coordinator.keep_connection
            or coordinator.settings_refresh_needed
        )

        if coordinator.keep_connection and not settings_refresh_needed:
            await client.fetch_boost()

        await updates.update_all(
            settings_refresh_needed=settings_refresh_needed,
        )

        if settings_refresh_needed:
            coordinator.settings_refresh_needed = False
            
        coordinator.last_successful_update = dt_util.utcnow()            

        return client

    async def _async_update_method() -> FreshIntelliVent:
        """Update Fresh Intellivent Sky data."""
        if coordinator.copy_in_progress:
            return client

        async with update_lock:
            if coordinator.copy_in_progress:
                return client

            try:
                try:
                    return await _run_update()
                except Exception:
                    if not coordinator.keep_connection:
                        raise

                    _LOGGER.debug(
                        "Keep Connection update failed; reconnecting and retrying once",
                        exc_info=True,
                    )

                    try:
                        await client.disconnect()
                    finally:
                        _set_connection_status(
                            "connected" if client.is_connected else "disconnected"
                        )

                    await _connect_and_authenticate(
                        reset_device_information=True
                    )
                    return await _run_update()

            except Exception as err:
                raise UpdateFailed(f"Unable to fetch data: {err}") from err

            finally:
                if not coordinator.keep_connection:
                    try:
                        await client.disconnect()
                    except Exception as err:
                        _LOGGER.error(
                            "Couldn't disconnect from %s: %s",
                            address,
                            err,
                        )

                    _set_connection_status(
                        "connected" if client.is_connected else "disconnected"
                    )

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=_async_update_method,
        update_interval=timedelta(seconds=initial_update_interval),
    )

    coordinator.client = client
    coordinator.auth_key = auth_key
    coordinator.poll_interval = initial_poll_interval
    coordinator.keep_connection = initial_keep_connection
    coordinator.debug_logging = initial_debug_logging
    coordinator.hw_version = getattr(client, "hw_version", None)
    coordinator.sw_version = getattr(client, "sw_version", None)
    coordinator.ble_address = address
    coordinator.rssi = None
    coordinator.bluetooth_source = None
    coordinator.last_successful_update = None 
    coordinator.connection_status = "disconnected"    
    coordinator.settings_refresh_needed = True
    coordinator.old_software_version = False
    coordinator.copy_in_progress = False
    coordinator.boost_minutes = 15
    coordinator.boost_rpm = 2400
    coordinator.pause_minutes = 15
    coordinator.update_lock = update_lock
    coordinator.pending_updates = {
        update: None for update in ALL_UPDATES
    }
    coordinator.scheduled_modes = {
        NIGHT_MODE: _mode_from_storage(
            NIGHT_MODE,
            dt_time(22, 0),
            dt_time(7, 0),
            1200,
        ),
        SILENT_HOURS: _mode_from_storage(
            SILENT_HOURS,
            dt_time(23, 0),
            dt_time(6, 0),
            1000,
        ),
    }
    stored_rpm_settings = stored_schedule.get("normal_rpm_settings")
    coordinator.normal_rpm_settings = (
        stored_rpm_settings
        if isinstance(stored_rpm_settings, dict)
        else None
    )
    coordinator.scheduled_mode_lock = scheduled_mode_lock
    _refresh_debug_logger_level(hass, coordinator)

    updates = FetchAndUpdate(coordinator=coordinator, client=client)

    async def _async_set_poll_interval(seconds: int) -> None:
        """Set and save the user-selected poll interval."""
        coordinator.poll_interval = seconds

        hass.config_entries.async_update_entry(
            entry,
            options={
                **entry.options,
                POLL_INTERVAL_OPTION: seconds,
            },
        )

        if not coordinator.keep_connection:
            coordinator.update_interval = timedelta(seconds=seconds)

    async def _async_set_keep_connection(enabled: bool) -> None:
        """Enable or disable the persistent BLE connection."""
        if coordinator.keep_connection == enabled:
            return

        hass.config_entries.async_update_entry(
            entry,
            options={
                **entry.options,
                KEEP_CONNECTION_OPTION: enabled,
            },
        )

        if enabled:
            async with update_lock:
                coordinator.keep_connection = True
                coordinator.settings_refresh_needed = True
                coordinator.update_interval = timedelta(
                    seconds=KEEP_CONNECTION_INTERVAL
                )

            await coordinator.async_request_refresh()
            return

        async with update_lock:
            coordinator.keep_connection = False
            coordinator.update_interval = timedelta(
                seconds=coordinator.poll_interval
            )
            try:
                await client.disconnect()
            finally:
                _set_connection_status(
                    "connected" if client.is_connected else "disconnected"
                )

        await coordinator.async_request_refresh()

    async def _async_set_debug_logging(enabled: bool) -> None:
        """Enable or disable and save per-device diagnostic logging."""
        coordinator.debug_logging = enabled
        _refresh_debug_logger_level(hass, coordinator)

        hass.config_entries.async_update_entry(
            entry,
            options={
                **entry.options,
                DEBUG_LOGGING_OPTION: enabled,
            },
        )

    async def _async_save_scheduled_modes() -> None:
        """Persist scheduled modes and the normal RPM settings."""
        modes = {}
        for mode, values in coordinator.scheduled_modes.items():
            modes[mode] = {
                "enabled": values["enabled"],
                "active": values["active"],
                START_TIME_KEY: values[START_TIME_KEY].isoformat(),
                END_TIME_KEY: values[END_TIME_KEY].isoformat(),
                MAX_RPM_KEY: values[MAX_RPM_KEY],
            }

        await schedule_store.async_save(
            {
                "modes": modes,
                "normal_rpm_settings": coordinator.normal_rpm_settings,
            }
        )

    def _time_is_active(
        now: dt_time,
        start: dt_time,
        end: dt_time,
    ) -> bool:
        """Return whether now is inside a scheduled time range."""
        if start == end:
            return False
        if start < end:
            return start <= now < end
        return now >= start or now < end

    def _current_rpm_settings() -> dict[str, int]:
        """Return current RPM settings already held by the integration."""
        rpm_settings = {}
        update_modes = (
            (CONSTANT_SPEED_UPDATE, "constant_speed"),
            (AIRING_MODE_UPDATE, "airing"),
            (HUMIDITY_MODE_UPDATE, "humidity"),
            (TIMER_MODE_UPDATE, "timer"),
            (VOC_MODE_UPDATE, "voc"),
        )

        for update, mode in update_modes:
            pending = coordinator.pending_updates.get(update)
            if isinstance(pending, dict) and pending.get(RPM_KEY) is not None:
                rpm_settings[mode] = int(pending[RPM_KEY])
                continue

            values = coordinator.data.modes.get(mode)
            if isinstance(values, dict) and values.get(RPM_KEY) is not None:
                rpm_settings[mode] = int(values[RPM_KEY])

        rpm_settings["boost"] = int(coordinator.boost_rpm)
        return rpm_settings

    def _queue_rpm_settings(rpm_settings: dict[str, int]) -> None:
        """Queue RPM settings while preserving all companion values."""
        update_modes = (
            (CONSTANT_SPEED_UPDATE, "constant_speed"),
            (AIRING_MODE_UPDATE, "airing"),
            (HUMIDITY_MODE_UPDATE, "humidity"),
            (TIMER_MODE_UPDATE, "timer"),
            (VOC_MODE_UPDATE, "voc"),
        )

        for update, mode in update_modes:
            if mode not in rpm_settings:
                continue

            pending = deepcopy(coordinator.pending_updates.get(update))
            if pending is None:
                current = coordinator.data.modes.get(mode)
                if not isinstance(current, dict):
                    continue
                pending = deepcopy(current)

            pending[RPM_KEY] = int(rpm_settings[mode])
            coordinator.pending_updates[update] = pending

        if "boost" in rpm_settings:
            coordinator.boost_rpm = int(rpm_settings["boost"])
            boost = coordinator.data.modes.get("boost")
            if isinstance(boost, dict) and boost.get("active", False):
                coordinator.pending_updates[BOOST_UPDATE] = {
                    ENABLED_KEY: True,
                    MINUTES_KEY: int(coordinator.boost_minutes),
                    RPM_KEY: coordinator.boost_rpm,
                }

        coordinator.settings_refresh_needed = True

    async def _async_update_scheduled_modes(*, force: bool = False) -> None:
        """Activate, change, or restore scheduled RPM modes."""
        write_needed = False

        async with scheduled_mode_lock:
            now = dt_util.now().time()
            previously_active = {
                mode
                for mode, values in coordinator.scheduled_modes.items()
                if values["active"]
            }
            active_modes = {
                mode
                for mode, values in coordinator.scheduled_modes.items()
                if values["enabled"]
                and _time_is_active(
                    now,
                    values[START_TIME_KEY],
                    values[END_TIME_KEY],
                )
            }

            if not force and active_modes == previously_active:
                return

            for mode, values in coordinator.scheduled_modes.items():
                values["active"] = mode in active_modes

            if active_modes:
                if not previously_active:
                    coordinator.normal_rpm_settings = _current_rpm_settings()

                target_rpm = min(
                    coordinator.scheduled_modes[mode][MAX_RPM_KEY]
                    for mode in active_modes
                )
                normal_rpm_settings = (
                    coordinator.normal_rpm_settings
                    or _current_rpm_settings()
                )
                target_settings = {
                    mode: min(int(normal_rpm), target_rpm)
                    for mode, normal_rpm in normal_rpm_settings.items()
                }
                _queue_rpm_settings(target_settings)
                write_needed = True
            elif previously_active and coordinator.normal_rpm_settings:
                _queue_rpm_settings(coordinator.normal_rpm_settings)
                write_needed = True

            await _async_save_scheduled_modes()

        if write_needed and not coordinator.keep_connection:
            await coordinator.async_request_refresh()

    async def _async_set_scheduled_mode_enabled(
        mode: str,
        enabled: bool,
    ) -> None:
        """Enable or disable one scheduled mode."""
        coordinator.scheduled_modes[mode]["enabled"] = enabled
        await _async_save_scheduled_modes()
        await _async_update_scheduled_modes(force=True)

    async def _async_set_scheduled_mode_time(
        mode: str,
        time_key: str,
        value: dt_time,
    ) -> None:
        """Set a start or end time for one scheduled mode."""
        coordinator.scheduled_modes[mode][time_key] = value
        await _async_save_scheduled_modes()
        await _async_update_scheduled_modes(force=True)

    async def _async_set_scheduled_mode_max_rpm(
        mode: str,
        value: int,
    ) -> None:
        """Set the maximum RPM for one scheduled mode."""
        coordinator.scheduled_modes[mode][MAX_RPM_KEY] = min(
            2400,
            max(850, value),
        )
        await _async_save_scheduled_modes()
        await _async_update_scheduled_modes(force=True)

    coordinator.async_set_poll_interval = _async_set_poll_interval
    coordinator.async_set_keep_connection = _async_set_keep_connection
    coordinator.async_set_debug_logging = _async_set_debug_logging
    coordinator.async_set_scheduled_mode_enabled = (
        _async_set_scheduled_mode_enabled
    )
    coordinator.async_set_scheduled_mode_time = _async_set_scheduled_mode_time
    coordinator.async_set_scheduled_mode_max_rpm = (
        _async_set_scheduled_mode_max_rpm
    )

    await coordinator.async_config_entry_first_refresh()

    await _async_update_scheduled_modes(force=True)

    @callback
    def _scheduled_mode_tick(now: datetime) -> None:
        """Check whether a scheduled mode should change state."""
        hass.async_create_task(_async_update_scheduled_modes())

    coordinator.scheduled_mode_unsub = async_track_time_interval(
        hass,
        _scheduled_mode_tick,
        timedelta(seconds=SCHEDULE_CHECK_INTERVAL),
    )

    hass.data[DOMAIN]["devices"][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(
        entry,
        READ_ONLY_PLATFORMS if auth_key is None else AUTHENTICATED_PLATFORMS,
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload a config entry."""
    coordinator = hass.data[DOMAIN]["devices"].get(entry.entry_id)

    if coordinator is not None:
        if scheduled_mode_unsub := getattr(
            coordinator,
            "scheduled_mode_unsub",
            None,
        ):
            scheduled_mode_unsub()

        try:
            async with coordinator.update_lock:
                await coordinator.client.disconnect()
        except Exception as err: 
            _LOGGER.debug(
                "Could not disconnect Fresh Intellivent Sky during unload: %s",
                err,
            )

    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry,
        AUTHENTICATED_PLATFORMS,
    ):
        hass.data[DOMAIN]["devices"].pop(entry.entry_id, None)
        _refresh_debug_logger_level(hass)

    return unload_ok