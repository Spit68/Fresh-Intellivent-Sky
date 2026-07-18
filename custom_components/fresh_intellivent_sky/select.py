"""Support for sensors."""
from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from .helpers import DETECTION_HIGH, DETECTION_LOW, DETECTION_MEDIUM

if TYPE_CHECKING:
    from .fresh_intellivent import FreshIntelliVent

from .const import (
    DOMAIN,
    HUMIDITY_MODE_UPDATE,
    LIGHT_AND_VOC_MODE_UPDATE,
    DETECTION_KEY,
    ENABLED_KEY,
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

    entities = [
            FreshIntelliventSkySelect(
                coordinator,
                coordinator.data,
                SelectEntityDescription(
                    key="humidity_detection",
                    translation_key="humidity_detection",
                ),
                keys=["humidity", DETECTION_KEY],
            ),
            FreshIntelliventSkySelect(
                coordinator,
                coordinator.data,
                SelectEntityDescription(
                    key="light_detection",
                    translation_key="light_detection",
                ),
                keys=["light_and_voc", "light", DETECTION_KEY],
            ),
            FreshIntelliventSkySelect(
                coordinator,
                coordinator.data,
                SelectEntityDescription(
                    key="voc_detection",
                    translation_key="voc_detection",
                ),
                keys=["light_and_voc", "voc", DETECTION_KEY],
            ),
        ]

    domain_data = hass.data[DOMAIN]
    domain_data.setdefault("copy_from_entry_id", None)
    domain_data.setdefault("copy_to_entry_id", None)
    domain_data.setdefault("copy_select_entities", [])

    copy_from = FreshIntelliventSkyCopySelect(
        hass,
        coordinator,
        coordinator.data,
        SelectEntityDescription(
            key="copy_from_device",
            translation_key="copy_from_device",
            icon="mdi:content-copy",
        ),
        selection_key="copy_from_entry_id",
        excluded_selection_key="copy_to_entry_id",
    )
    copy_to = FreshIntelliventSkyCopySelect(
        hass,
        coordinator,
        coordinator.data,
        SelectEntityDescription(
            key="copy_to_device",
            translation_key="copy_to_device",
            icon="mdi:content-duplicate",
        ),
        selection_key="copy_to_entry_id",
        excluded_selection_key="copy_from_entry_id",
    )

    domain_data["copy_select_entities"].extend([copy_from, copy_to])
    entities.extend([copy_from, copy_to])

    async_add_entities(entities)


class FreshIntelliventSkyCopySelect(
    CoordinatorEntity[DataUpdateCoordinator[Any]], SelectEntity
):
    """Select the source or destination SKY for copying settings."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DataUpdateCoordinator,
        device: FreshIntelliVent,
        entity_description: SelectEntityDescription,
        selection_key: str,
        excluded_selection_key: str,
    ) -> None:
        """Initialize a shared copy-device select."""
        super().__init__(coordinator)
        self.hass = hass
        self.entity_description = entity_description
        self._selection_key = selection_key
        self._excluded_selection_key = excluded_selection_key

        name = f"{device.manufacturer} {device.name}"

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
            model=device.model,
            hw_version=device.hw_version,
            sw_version=device.sw_version,
        )

    def _device_labels(self) -> dict[str, str]:
        """Return entry IDs mapped to unique visible device labels."""
        devices = self.hass.data[DOMAIN]["devices"]
        labels: dict[str, str] = {}
        used_labels: set[str] = set()

        sorted_devices = []

        for entry_id, coordinator in devices.items():
            entry = self.hass.config_entries.async_get_entry(entry_id)
            label = entry.title if entry is not None else coordinator.data.name
            sorted_devices.append((entry_id, coordinator, label))

        sorted_devices.sort(key=lambda item: item[2].casefold())

        for entry_id, coordinator, label in sorted_devices:
            if label in used_labels:
                address = coordinator.data.address
                label = f"{label} ({address[-5:]})"

            used_labels.add(label)
            labels[entry_id] = label

        return labels

    @property
    def available(self) -> bool:
        """Return whether copying is available."""
        return len(self.hass.data[DOMAIN]["devices"]) > 1

    @property
    def options(self) -> list[str]:
        """Return all selectable SKY devices."""
        return list(self._device_labels().values())

    @property
    def current_option(self) -> str | None:
        """Return the currently selected device."""
        selected_entry_id = self.hass.data[DOMAIN].get(
            self._selection_key
        )
        return self._device_labels().get(selected_entry_id)

    async def async_select_option(self, option: str) -> None:
        """Select a SKY device."""
        labels = self._device_labels()
        selected_entry_id = next(
            (
                entry_id
                for entry_id, label in labels.items()
                if label == option
            ),
            None,
        )

        if selected_entry_id is None:
            raise ValueError(f"Unknown Fresh Intellivent SKY device: {option}")

        self.hass.data[DOMAIN][self._selection_key] = selected_entry_id

        for entity in self.hass.data[DOMAIN]["copy_select_entities"]:
            entity.async_write_ha_state()

        for coordinator in self.hass.data[DOMAIN]["devices"].values():
            coordinator.async_update_listeners()


class FreshIntelliventSkySelect(
    CoordinatorEntity[DataUpdateCoordinator[Any]], SelectEntity
):
    """Fresh Intellivent Sky numbers for the device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: FreshIntelliVent,
        entity_description: SelectEntityDescription,
        keys: list | None = None,
    ) -> None:
        """Populate the entity with relevant data."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        name = f"{device.manufacturer} {device.name}"

        self._attr_unique_id = f"{device.manufacturer}_{name}_{entity_description.key}"
        self._attr_entity_category = EntityCategory.CONFIG
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

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        return [DETECTION_LOW, DETECTION_MEDIUM, DETECTION_HIGH]

    @property
    def current_option(self) -> str | None:
        """Return the value reported value."""
        if self._keys is None:
            return None
        value = self.coordinator.data.modes
        for key in self._keys:
            if value.get(key) is None:
                return None
            value = value[key]

        return value

    async def async_select_option(self, option: str) -> None:
        """Set the detection level while preserving enabled states."""
        key = self.entity_description.key

        if key == "humidity_detection":
            humidity = deepcopy(
                self.coordinator.pending_updates.get(HUMIDITY_MODE_UPDATE)
                or self.coordinator.data.modes["humidity"]
            )
            humidity[DETECTION_KEY] = option
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

            if key == "light_detection":
                pending["light_detection"] = option
            else:
                pending["voc_detection"] = option

            self.coordinator.pending_updates[LIGHT_AND_VOC_MODE_UPDATE] = pending
        if not self.coordinator.keep_connection:
            await self.coordinator.async_request_refresh()