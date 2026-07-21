"""Support for scheduled mode times."""
from __future__ import annotations

from datetime import time
from typing import Any, TYPE_CHECKING

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
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
    DOMAIN,
    END_TIME_KEY,
    NIGHT_MODE,
    SILENT_HOURS,
    START_TIME_KEY,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up scheduled mode time entities."""
    coordinator: DataUpdateCoordinator[FreshIntelliVent] = hass.data[DOMAIN][
        "devices"
    ][config_entry.entry_id]

    async_add_entities(
        [
            FreshIntelliventScheduledModeTime(
                coordinator,
                coordinator.data,
                TimeEntityDescription(
                    key="night_mode_start_time",
                    translation_key="night_mode_start_time",
                ),
                mode=NIGHT_MODE,
                time_key=START_TIME_KEY,
            ),
            FreshIntelliventScheduledModeTime(
                coordinator,
                coordinator.data,
                TimeEntityDescription(
                    key="night_mode_end_time",
                    translation_key="night_mode_end_time",
                ),
                mode=NIGHT_MODE,
                time_key=END_TIME_KEY,
            ),
            FreshIntelliventScheduledModeTime(
                coordinator,
                coordinator.data,
                TimeEntityDescription(
                    key="silent_hours_start_time",
                    translation_key="silent_hours_start_time",
                ),
                mode=SILENT_HOURS,
                time_key=START_TIME_KEY,
            ),
            FreshIntelliventScheduledModeTime(
                coordinator,
                coordinator.data,
                TimeEntityDescription(
                    key="silent_hours_end_time",
                    translation_key="silent_hours_end_time",
                ),
                mode=SILENT_HOURS,
                time_key=END_TIME_KEY,
            ),
        ]
    )


class FreshIntelliventScheduledModeTime(
    CoordinatorEntity[DataUpdateCoordinator[Any]], TimeEntity
):
    """A start or end time for a scheduled RPM mode."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:clock-outline"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: FreshIntelliVent,
        entity_description: TimeEntityDescription,
        mode: str,
        time_key: str,
    ) -> None:
        """Initialize a scheduled mode time entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        name = f"{device.manufacturer} {device.name}"

        self._mode = mode
        self._time_key = time_key
        self._attr_unique_id = (
            f"{device.manufacturer}_{name}_{entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            connections={
                (
                    CONNECTION_BLUETOOTH,
                    device.address,
                )
            },
            name=name,
            manufacturer=device.manufacturer,
            hw_version=device.hw_version,
            sw_version=device.sw_version,
        )

    @property
    def native_value(self) -> time:
        """Return the configured time."""
        return self.coordinator.scheduled_modes[self._mode][self._time_key]

    async def async_set_value(self, value: time) -> None:
        """Set the configured time."""
        await self.coordinator.async_set_scheduled_mode_time(
            self._mode,
            self._time_key,
            value,
        )
        self.async_write_ha_state()