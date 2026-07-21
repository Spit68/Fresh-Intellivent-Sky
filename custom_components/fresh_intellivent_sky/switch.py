"""Support for switches."""
from __future__ import annotations

from copy import deepcopy
from typing import cast, TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
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
    CONSTANT_SPEED_UPDATE,
    DOMAIN,
    ENABLED_KEY,
    DETECTION_KEY,
    HUMIDITY_MODE_UPDATE,
    LIGHT_AND_VOC_MODE_UPDATE,
    NIGHT_MODE,
    SILENT_HOURS,
)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors dynamically through discovery."""
    coordinator: DataUpdateCoordinator[FreshIntelliVent] = hass.data[DOMAIN][
        "devices"
    ][config_entry.entry_id]

    async_add_entities(
        [
            FreshIntelliventSkySwitch(
                coordinator,
                coordinator.data,
                SwitchEntityDescription(
                    key="constant_speed_enabled",
                    translation_key="constant_speed_enabled",
                ),
                entity_category=EntityCategory.CONFIG,
                keys=["constant_speed", ENABLED_KEY],
            ),
            FreshIntelliventSkySwitch(
                coordinator,
                coordinator.data,
                SwitchEntityDescription(
                    key="humidity_detection_enabled",
                    translation_key="humidity_detection_enabled",
                ),
                entity_category=EntityCategory.CONFIG,
                keys=["humidity", ENABLED_KEY],
            ),
            FreshIntelliventSkySwitch(
                coordinator,
                coordinator.data,
                SwitchEntityDescription(
                    key="light_detection_enabled",
                    translation_key="light_detection_enabled",
                ),
                entity_category=EntityCategory.CONFIG,
                keys=["light_and_voc", "light", ENABLED_KEY],
            ),
            FreshIntelliventSkySwitch(
                coordinator,
                coordinator.data,
                SwitchEntityDescription(
                    key="voc_detection_enabled",
                    translation_key="voc_detection_enabled",
                ),
                entity_category=EntityCategory.CONFIG,
                keys=["light_and_voc", "voc", ENABLED_KEY],
            ),
            FreshIntelliventKeepConnectionSwitch(
                coordinator,
                coordinator.data,
            ),
            FreshIntelliventDebugLoggingSwitch(
                coordinator,
                coordinator.data,
            ),
            FreshIntelliventScheduledModeSwitch(
                coordinator,
                coordinator.data,
                mode=NIGHT_MODE,
                icon="mdi:weather-night",
            ),
            FreshIntelliventScheduledModeSwitch(
                coordinator,
                coordinator.data,
                mode=SILENT_HOURS,
                icon="mdi:volume-off",
            ),
        ]
    )


class FreshIntelliventSkySwitch(
    CoordinatorEntity[DataUpdateCoordinator[Any]], SwitchEntity
):
    """Fresh Intellivent Sky numbers for the device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: FreshIntelliVent,
        entity_description: SwitchEntityDescription,
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
            hw_version=device.hw_version,
            sw_version=device.sw_version,
        )

    @property
    def is_on(self) -> bool:
        """Return the value reported by the sensor."""
        if self._keys is None:
            return None
        value = self.coordinator.data.modes
        for key in self._keys:
            if value.get(key) is None:
                return None
            value = value[key]

        return cast(bool, value)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on."""
        await self.update_state(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off."""
        await self.update_state(False)

    async def update_state(self, new_value: bool) -> None:
        """Update state while preserving companion settings."""
        key = self.entity_description.key

        if key == "constant_speed_enabled":
            constant_speed = deepcopy(
                self.coordinator.pending_updates.get(CONSTANT_SPEED_UPDATE)
                or self.coordinator.data.modes["constant_speed"]
            )
            constant_speed[ENABLED_KEY] = new_value
            self.coordinator.pending_updates[CONSTANT_SPEED_UPDATE] = constant_speed

        elif key == "humidity_detection_enabled":
            humidity = deepcopy(
                self.coordinator.pending_updates.get(HUMIDITY_MODE_UPDATE)
                or self.coordinator.data.modes["humidity"]
            )
            humidity[ENABLED_KEY] = new_value
            self.coordinator.pending_updates[HUMIDITY_MODE_UPDATE] = humidity

        else:
            pending = deepcopy(
                self.coordinator.pending_updates.get(LIGHT_AND_VOC_MODE_UPDATE)
            )
            if pending is None:
                light = self.coordinator.data.modes["light_and_voc"]["light"]
                voc = self.coordinator.data.modes["light_and_voc"]["voc"]
                pending = {
                    "light_enabled": light[ENABLED_KEY],
                    "light_detection": light[DETECTION_KEY],
                    "voc_enabled": voc[ENABLED_KEY],
                    "voc_detection": voc[DETECTION_KEY],
                }

            if key == "light_detection_enabled":
                pending["light_enabled"] = new_value
            elif key == "voc_detection_enabled":
                pending["voc_enabled"] = new_value

            self.coordinator.pending_updates[LIGHT_AND_VOC_MODE_UPDATE] = pending

        if not self.coordinator.keep_connection:
            await self.coordinator.async_request_refresh()

class FreshIntelliventKeepConnectionSwitch(
    CoordinatorEntity[DataUpdateCoordinator[Any]], SwitchEntity
):
    """Keep the BLE connection open for faster live updates."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "keep_connection"
    _attr_icon = "mdi:bluetooth-connect"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: FreshIntelliVent,
    ) -> None:
        """Initialize the Keep Connection switch."""
        super().__init__(coordinator)

        name = f"{device.manufacturer} {device.name}"

        self._attr_unique_id = f"{device.manufacturer}_{name}_keep_connection"
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
    def is_on(self) -> bool:
        """Return whether Keep Connection is enabled."""
        return self.coordinator.keep_connection

    async def async_turn_on(self, **kwargs) -> None:
        """Enable Keep Connection."""
        await self.coordinator.async_set_keep_connection(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable Keep Connection."""
        await self.coordinator.async_set_keep_connection(False)
        self.async_write_ha_state()


class FreshIntelliventScheduledModeSwitch(
    CoordinatorEntity[DataUpdateCoordinator[Any]], SwitchEntity
):
    """Enable or disable a scheduled RPM mode for one SKY."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: FreshIntelliVent,
        mode: str,
        icon: str,
    ) -> None:
        """Initialize a scheduled RPM mode switch."""
        super().__init__(coordinator)

        name = f"{device.manufacturer} {device.name}"

        self._mode = mode
        self._attr_translation_key = mode
        self._attr_icon = icon
        self._attr_unique_id = f"{device.manufacturer}_{name}_{mode}"
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
    def is_on(self) -> bool:
        """Return whether the scheduled RPM mode is enabled."""
        return self.coordinator.scheduled_modes[self._mode]["enabled"]

    async def async_turn_on(self, **kwargs) -> None:
        """Enable the scheduled RPM mode."""
        await self.coordinator.async_set_scheduled_mode_enabled(self._mode, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable the scheduled RPM mode."""
        await self.coordinator.async_set_scheduled_mode_enabled(self._mode, False)
        self.async_write_ha_state()


class FreshIntelliventDebugLoggingSwitch(
    CoordinatorEntity[DataUpdateCoordinator[Any]], SwitchEntity
):
    """Enable detailed diagnostic logging for one SKY."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "debug_logs"
    _attr_icon = "mdi:bug"

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: FreshIntelliVent,
    ) -> None:
        """Initialize the debug logging switch."""
        super().__init__(coordinator)

        name = f"{device.manufacturer} {device.name}"

        self._attr_unique_id = f"{device.manufacturer}_{name}_debug_logs"
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
    def is_on(self) -> bool:
        """Return whether detailed diagnostic logging is enabled."""
        return self.coordinator.debug_logging

    async def async_turn_on(self, **kwargs) -> None:
        """Enable detailed diagnostic logging."""
        await self.coordinator.async_set_debug_logging(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable detailed diagnostic logging."""
        await self.coordinator.async_set_debug_logging(False)
        self.async_write_ha_state()