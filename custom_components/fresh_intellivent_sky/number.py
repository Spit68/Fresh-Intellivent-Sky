"""Support for numbers."""
from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import REVOLUTIONS_PER_MINUTE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

if TYPE_CHECKING:
    from .fresh_intellivent import FreshIntelliVent

from .const import (
    AIRING_MODE_UPDATE,
    BOOST_UPDATE,
    CONSTANT_SPEED_UPDATE,
    DELAY_KEY,
    DETECTION_KEY,
    DOMAIN,
    ENABLED_KEY,
    HUMIDITY_MODE_UPDATE,
    MAX_RPM_KEY,
    MINUTES_KEY,
    NIGHT_MODE,
    PAUSE_UPDATE,
    RPM_KEY,
    SILENT_HOURS,
    TIMER_MODE_UPDATE,
    VOC_MODE_UPDATE,
)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up numbers dynamically through discovery."""
    coordinator: DataUpdateCoordinator[FreshIntelliVent] = hass.data[DOMAIN][
        "devices"
    ][config_entry.entry_id]

    entities = [
        FreshIntelliventSkyNumber(
            coordinator,
            coordinator.data,
            NumberEntityDescription(
                key="humidity_rpm",
                translation_key=(
                    "humidity_rpm"
                    if not coordinator.old_software_version
                    else "humidity_voc_rpm"
                ),
                native_min_value=800,
                native_max_value=2400,
                native_step=1,
                native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
            ),
            entity_category=EntityCategory.CONFIG,
            keys=["humidity", "rpm"],
        ),
    ]

    if not coordinator.old_software_version:
        entities.append(
            FreshIntelliventSkyNumber(
                coordinator,
                coordinator.data,
                NumberEntityDescription(
                    key="voc_rpm",
                    translation_key="voc_rpm",
                    native_min_value=800,
                    native_max_value=2400,
                    native_step=1,
                    native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
                ),
                entity_category=EntityCategory.CONFIG,
                keys=["voc", "rpm"],
            )
        )

    entities.extend(
        [
            FreshIntelliventSkyNumber(
                coordinator,
                coordinator.data,
                NumberEntityDescription(
                    key="constant_speed_rpm",
                    translation_key="constant_speed_rpm",
                    native_min_value=850,
                    native_max_value=2400,
                    native_step=1,
                    native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
                ),
                entity_category=EntityCategory.CONFIG,
                keys=["constant_speed", "rpm"],
            ),
            FreshIntelliventSkyNumber(
                coordinator,
                coordinator.data,
                NumberEntityDescription(
                    key="airing_rpm",
                    translation_key="airing_rpm",
                    native_min_value=800,
                    native_max_value=2400,
                    native_step=1,
                    native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
                ),
                entity_category=EntityCategory.CONFIG,
                keys=["airing", "rpm"],
            ),
            FreshIntelliventSkyNumber(
                coordinator,
                coordinator.data,
                NumberEntityDescription(
                    key="boost_rpm",
                    translation_key="boost_rpm",
                    native_min_value=800,
                    native_max_value=2400,
                    native_step=50,
                    native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
                ),
                entity_category=EntityCategory.CONFIG,
                keys=None,
            ),            
            FreshIntelliventSkyNumber(
                coordinator,
                coordinator.data,
                NumberEntityDescription(
                    key="airing_minutes",
                    translation_key="airing_minutes",
                    native_min_value=5,
                    native_max_value=120,
                    native_step=1,
                    native_unit_of_measurement=UnitOfTime.MINUTES,
                ),
                entity_category=EntityCategory.CONFIG,
                keys=["airing", "minutes"],
            ),
            FreshIntelliventSkyNumber(
                coordinator,
                coordinator.data,
                NumberEntityDescription(
                    key="boost_minutes",
                    translation_key="boost_minutes",
                    native_min_value=1,
                    native_max_value=60,
                    native_step=1,
                    native_unit_of_measurement=UnitOfTime.MINUTES,
                ),
                entity_category=EntityCategory.CONFIG,
                keys=None,
            ),            
            FreshIntelliventSkyNumber(
                coordinator,
                coordinator.data,
                NumberEntityDescription(
                    key="pause_minutes",
                    translation_key="pause_minutes",
                    native_min_value=1,
                    native_max_value=120,
                    native_step=1,
                    native_unit_of_measurement=UnitOfTime.MINUTES,
                    mode=NumberMode.SLIDER,
                ),
                entity_category=EntityCategory.CONFIG,
                keys=None,
            ),
            FreshIntelliventSkyNumber(
                coordinator,
                coordinator.data,
                NumberEntityDescription(
                    key="timer_and_light_rpm",
                    translation_key="timer_and_light_rpm",
                    native_min_value=800,
                    native_max_value=2400,
                    native_step=1,
                    native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
                ),
                entity_category=EntityCategory.CONFIG,
                keys=["timer", "rpm"],
            ),
            FreshIntelliventSkyNumber(
                coordinator,
                coordinator.data,
                NumberEntityDescription(
                    key="timer_minutes",
                    translation_key="timer_minutes",
                    native_min_value=5,
                    native_max_value=60,
                    native_step=1,
                    native_unit_of_measurement=UnitOfTime.MINUTES,
                ),
                entity_category=EntityCategory.CONFIG,
                keys=["timer", "minutes"],
            ),
            FreshIntelliventSkyNumber(
                coordinator,
                coordinator.data,
                NumberEntityDescription(
                    key="night_mode_max_rpm",
                    translation_key="night_mode_max_rpm",
                    native_min_value=850,
                    native_max_value=2400,
                    native_step=1,
                    native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
                ),
                entity_category=EntityCategory.CONFIG,
                keys=None,
            ),
            FreshIntelliventSkyNumber(
                coordinator,
                coordinator.data,
                NumberEntityDescription(
                    key="silent_hours_max_rpm",
                    translation_key="silent_hours_max_rpm",
                    native_min_value=850,
                    native_max_value=2400,
                    native_step=1,
                    native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
                ),
                entity_category=EntityCategory.CONFIG,
                keys=None,
            ),
            FreshIntelliventSkyNumber(
                coordinator,
                coordinator.data,
                NumberEntityDescription(
                    key="poll_interval",
                    translation_key="poll_interval",
                    native_min_value=10,
                    native_max_value=300,
                    native_step=1,
                    native_unit_of_measurement=UnitOfTime.SECONDS,
                ),
                entity_category=EntityCategory.CONFIG,
                keys=None,
            ),
            FreshIntelliventSkyNumber(
                coordinator,
                coordinator.data,
                NumberEntityDescription(
                    key="timer_delay_minutes",
                    translation_key="timer_delay_minutes",
                    native_min_value=0,
                    native_max_value=10,
                    native_step=1,
                    native_unit_of_measurement=UnitOfTime.MINUTES,
                ),
                entity_category=EntityCategory.CONFIG,
                keys=["timer", "delay", "minutes"],
            ),
        ]
    )

    async_add_entities(entities)

class FreshIntelliventSkyNumber(
    CoordinatorEntity[DataUpdateCoordinator[Any]], NumberEntity
):
    """Fresh Intellivent numbers for the device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: FreshIntelliVent,
        entity_description: NumberEntityDescription,
        entity_category: EntityCategory | None = None,
        keys: list | None = None,
    ) -> None:
        """Populate the entity with relevant data."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        name = f"{device.manufacturer} {device.name}"

        self._attr_unique_id = f"{device.manufacturer}_{name}_{entity_description.key}"
        self._attr_entity_category = entity_category
        self._keys = keys
        self._attr_device_info = DeviceInfo(
            connections={
                (
                    CONNECTION_BLUETOOTH,
                    device.address,
                )
            },
            name=name,
            manufacturer=device.manufacturer,
            model=device.model,
            hw_version=device.hw_version,
            sw_version=device.sw_version,
        )
        if entity_description.key == "boost_minutes":
            self._boost_duration = int(
                getattr(self.coordinator, "boost_minutes", 15)
            )
            self.coordinator.boost_minutes = self._boost_duration
        else:
            self._boost_duration = None

        if entity_description.key == "boost_rpm":
            self._boost_rpm = int(
                getattr(self.coordinator, "boost_rpm", 2400)
            )
            self.coordinator.boost_rpm = self._boost_rpm
        else:
            self._boost_rpm = None

        if entity_description.key == "pause_minutes":
            self._pause_duration = int(
                getattr(self.coordinator, "pause_minutes", 15)
            )
            self.coordinator.pause_minutes = self._pause_duration
        else:
            self._pause_duration = None

    @property
    def native_value(self) -> float | None:
        """Return the reported value."""
        if self.entity_description.key == "boost_minutes":
            return self.coordinator.boost_minutes
            
        if self.entity_description.key == "boost_rpm":
            return self.coordinator.boost_rpm

        if self.entity_description.key == "pause_minutes":
            return self.coordinator.pause_minutes

        if self.entity_description.key == "poll_interval":
            return self.coordinator.poll_interval

        if self.entity_description.key == "night_mode_max_rpm":
            return self.coordinator.scheduled_modes[NIGHT_MODE][MAX_RPM_KEY]

        if self.entity_description.key == "silent_hours_max_rpm":
            return self.coordinator.scheduled_modes[SILENT_HOURS][MAX_RPM_KEY]

        if self._keys is None:
            return None

        value = self.coordinator.data.modes
        for key in self._keys:
            if value.get(key) is None:
                return None
            value = value[key]

        return value

    def _boost_is_active(self) -> bool:
        """Return whether Boost is currently active."""
        boost = self.coordinator.data.modes.get("boost")

        if not isinstance(boost, dict):
            return False

        return bool(boost.get("active", False))

    async def _send_live_boost_update(self) -> None:
        """Send the locally selected Boost values while Boost is active."""
        minutes = int(getattr(self.coordinator, "boost_minutes", 15))
        rpm = int(getattr(self.coordinator, "boost_rpm", 2400))

        self.coordinator.pending_updates[BOOST_UPDATE] = {
            ENABLED_KEY: True,
            MINUTES_KEY: minutes,
            RPM_KEY: rpm,
        }

        if not self.coordinator.keep_connection:
            await self.coordinator.async_request_refresh()

    def _pause_is_active(self) -> bool:
        """Return whether Pause is currently active."""
        pause = self.coordinator.data.modes.get("pause")

        if not isinstance(pause, dict):
            return False

        return bool(pause.get(ENABLED_KEY, False))

    async def _send_live_pause_update(self, minutes: int) -> None:
        """Send the selected Pause duration while Pause is active."""
        self.coordinator.pending_updates[PAUSE_UPDATE] = {
            ENABLED_KEY: True,
            MINUTES_KEY: int(minutes),
        }

        if not self.coordinator.keep_connection:
            await self.coordinator.async_request_refresh()

    async def async_set_native_value(self, value: float) -> None:
        """Set value."""
        key = self.entity_description.key

        if key == "humidity_rpm":
            humidity = deepcopy(
                self.coordinator.pending_updates.get(HUMIDITY_MODE_UPDATE)
                or self.coordinator.data.modes["humidity"]
            )
            humidity[RPM_KEY] = int(value)
            self.coordinator.pending_updates[HUMIDITY_MODE_UPDATE] = humidity
        elif key == "voc_rpm":
            voc = deepcopy(
                self.coordinator.pending_updates.get(VOC_MODE_UPDATE)
                or self.coordinator.data.modes["voc"]
            )
            voc[RPM_KEY] = int(value)
            self.coordinator.pending_updates[VOC_MODE_UPDATE] = voc
        elif key == "constant_speed_rpm":
            constant_speed = deepcopy(
                self.coordinator.pending_updates.get(CONSTANT_SPEED_UPDATE)
                or self.coordinator.data.modes["constant_speed"]
            )
            constant_speed[RPM_KEY] = int(value)
            self.coordinator.pending_updates[CONSTANT_SPEED_UPDATE] = constant_speed
        elif key == "airing_rpm":
            airing = deepcopy(
                self.coordinator.pending_updates.get(AIRING_MODE_UPDATE)
                or self.coordinator.data.modes["airing"]
            )
            airing[RPM_KEY] = int(value)
            self.coordinator.pending_updates[AIRING_MODE_UPDATE] = airing
        elif key == "airing_minutes":
            airing = deepcopy(
                self.coordinator.pending_updates.get(AIRING_MODE_UPDATE)
                or self.coordinator.data.modes["airing"]
            )
            airing[MINUTES_KEY] = int(value)
            self.coordinator.pending_updates[AIRING_MODE_UPDATE] = airing
        elif key == "timer_and_light_rpm":
            timer = deepcopy(
                self.coordinator.pending_updates.get(TIMER_MODE_UPDATE)
                or self.coordinator.data.modes["timer"]
            )
            timer[RPM_KEY] = int(value)
            self.coordinator.pending_updates[TIMER_MODE_UPDATE] = timer
        elif key == "timer_minutes":
            timer = deepcopy(
                self.coordinator.pending_updates.get(TIMER_MODE_UPDATE)
                or self.coordinator.data.modes["timer"]
            )
            timer[MINUTES_KEY] = int(value)
            self.coordinator.pending_updates[TIMER_MODE_UPDATE] = timer
        elif key == "timer_delay_minutes":
            delay_minutes = int(value)
            delay_enabled = delay_minutes > 0

            timer = deepcopy(
                self.coordinator.pending_updates.get(TIMER_MODE_UPDATE)
                or self.coordinator.data.modes["timer"]
            )
            timer[DELAY_KEY] = {
                ENABLED_KEY: delay_enabled,
                MINUTES_KEY: delay_minutes,
            }
            self.coordinator.pending_updates[TIMER_MODE_UPDATE] = timer
        elif key == "boost_minutes":
            self._boost_duration = int(value)
            self.coordinator.boost_minutes = self._boost_duration
            self.async_write_ha_state()

            if self._boost_is_active():
                await self._send_live_boost_update()
            return

        elif key == "boost_rpm":
            self._boost_rpm = int(value)
            self.coordinator.boost_rpm = self._boost_rpm
            self.async_write_ha_state()

            if self._boost_is_active():
                await self._send_live_boost_update()
            return

        elif key == "pause_minutes":
            self._pause_duration = int(value)
            self.coordinator.pause_minutes = self._pause_duration
            self.async_write_ha_state()

            if self._pause_is_active():
                await self._send_live_pause_update(self._pause_duration)
            return

        elif key == "poll_interval":
            await self.coordinator.async_set_poll_interval(int(value))
            self.async_write_ha_state()
            return

        elif key == "night_mode_max_rpm":
            await self.coordinator.async_set_scheduled_mode_max_rpm(
                NIGHT_MODE,
                int(value),
            )
            self.async_write_ha_state()
            return

        elif key == "silent_hours_max_rpm":
            await self.coordinator.async_set_scheduled_mode_max_rpm(
                SILENT_HOURS,
                int(value),
            )
            self.async_write_ha_state()
            return

        if not self.coordinator.keep_connection:
            await self.coordinator.async_request_refresh()