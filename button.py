"""Support for Fresh Intellivent SKY action buttons."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

if TYPE_CHECKING:
    from .fresh_intellivent import FreshIntelliVent

from .const import (
    BOOST_UPDATE,
    DELAY_KEY,
    DETECTION_KEY,
    DOMAIN,
    ENABLED_KEY,
    MINUTES_KEY,
    PAUSE_UPDATE,
    RPM_KEY,
    TIMEOUT,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Fresh Intellivent SKY buttons."""
    coordinator: DataUpdateCoordinator[FreshIntelliVent] = hass.data[DOMAIN][
        "devices"
    ][config_entry.entry_id]

    entities = [
        FreshIntelliventSkyActionButton(
            coordinator,
            coordinator.data,
            ButtonEntityDescription(
                key="start_boost",
                translation_key="start_boost",
                icon="mdi:fan-plus",
            ),
            action="boost",
            enabled=True,
        ),
        FreshIntelliventSkyActionButton(
            coordinator,
            coordinator.data,
            ButtonEntityDescription(
                key="cancel_boost",
                translation_key="cancel_boost",
                icon="mdi:fan-off",
            ),
            action="boost",
            enabled=False,
        ),
        FreshIntelliventSkyActionButton(
            coordinator,
            coordinator.data,
            ButtonEntityDescription(
                key="start_pause",
                translation_key="start_pause",
                icon="mdi:pause-circle",
            ),
            action="pause",
            enabled=True,
        ),
        FreshIntelliventSkyActionButton(
            coordinator,
            coordinator.data,
            ButtonEntityDescription(
                key="cancel_pause",
                translation_key="cancel_pause",
                icon="mdi:play-circle",
            ),
            action="pause",
            enabled=False,
        ),
    ]

    entities.append(
        FreshIntelliventSkyCopySettingsButton(
            hass,
            coordinator,
            coordinator.data,
            config_entry.entry_id,
            ButtonEntityDescription(
                key="duplicate_settings",
                translation_key="duplicate_settings",
                icon="mdi:content-duplicate",
            ),
        )
    )

    async_add_entities(entities)


class FreshIntelliventSkyCopySettingsButton(
    CoordinatorEntity[DataUpdateCoordinator[Any]], ButtonEntity
):
    """Copy settings from the selected source SKY to the destination SKY."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DataUpdateCoordinator,
        device: FreshIntelliVent,
        entry_id: str,
        entity_description: ButtonEntityDescription,
    ) -> None:
        """Initialize the copy-settings button for one destination SKY."""
        super().__init__(coordinator)
        self.hass = hass
        self._entry_id = entry_id
        self.entity_description = entity_description

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

    @property
    def available(self) -> bool:
        """Return whether both different devices have been selected."""
        domain_data = self.hass.data[DOMAIN]
        source_entry_id = domain_data.get("copy_from_entry_id")
        target_entry_id = domain_data.get("copy_to_entry_id")

        return (
            len(domain_data["devices"]) > 1
            and source_entry_id is not None
            and target_entry_id is not None
            and source_entry_id != target_entry_id
            and source_entry_id in domain_data["devices"]
            and target_entry_id in domain_data["devices"]
            and target_entry_id == self._entry_id
        )

    async def async_press(self) -> None:
        """Copy all supported settings to the selected destination SKY."""
        if not self.available:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="copy_devices_not_selected",
            )

        domain_data = self.hass.data[DOMAIN]
        source_entry_id = domain_data["copy_from_entry_id"]
        target_entry_id = domain_data["copy_to_entry_id"]

        if source_entry_id == target_entry_id:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="copy_same_device",
            )

        source = domain_data["devices"][source_entry_id]
        target = domain_data["devices"][target_entry_id]

        target.copy_in_progress = True
        await self._copy_settings(source, target)

    async def _copy_settings(
        self,
        source: DataUpdateCoordinator,
        target: DataUpdateCoordinator,
    ) -> None:
        """Copy HA-only values and write all supported settings directly."""
        source_modes = deepcopy(source.data.modes)

        constant_speed = source_modes["constant_speed"]
        airing = source_modes["airing"]
        humidity = source_modes["humidity"]
        light_and_voc = source_modes["light_and_voc"]
        timer = source_modes["timer"]

        expected_voc_rpm: int | None = None
        if not target.old_software_version:
            if source.old_software_version:
                expected_voc_rpm = int(humidity[RPM_KEY])
            else:
                expected_voc_rpm = int(source_modes["voc"][RPM_KEY])

        # These four values only exist in Home Assistant and are therefore
        # copied without writing anything to the source or destination SKY.
        target.boost_minutes = int(getattr(source, "boost_minutes", 15))
        target.boost_rpm = int(getattr(source, "boost_rpm", 2400))
        target.pause_minutes = int(getattr(source, "pause_minutes", 15))
        await target.async_set_poll_interval(
            int(getattr(source, "poll_interval", 30))
        )

        client = target.client
        should_disconnect = not target.keep_connection

        try:
            # The destination lock waits for an update already in progress and
            # prevents new destination updates during the complete copy.
            async with target.update_lock:
                if not client.is_connected:
                    await client.connect(timeout=TIMEOUT)

                    if target.auth_key is not None:
                        await client.authenticate(
                            authentication_code=target.auth_key
                        )

                await client.update_constant_speed(
                    enabled=bool(constant_speed[ENABLED_KEY]),
                    rpm=int(constant_speed[RPM_KEY]),
                )
                await asyncio.sleep(0.1)

                await client.update_airing(
                    enabled=bool(airing[ENABLED_KEY]),
                    minutes=int(airing[MINUTES_KEY]),
                    rpm=int(airing[RPM_KEY]),
                )
                await asyncio.sleep(0.1)

                await client.update_humidity(
                    enabled=bool(humidity[ENABLED_KEY]),
                    detection=humidity[DETECTION_KEY],
                    rpm=int(humidity[RPM_KEY]),
                )
                await asyncio.sleep(0.1)

                await client.update_light_and_voc(
                    light_enabled=bool(
                        light_and_voc["light"][ENABLED_KEY]
                    ),
                    light_detection=light_and_voc["light"][DETECTION_KEY],
                    voc_enabled=bool(
                        light_and_voc["voc"][ENABLED_KEY]
                    ),
                    voc_detection=light_and_voc["voc"][DETECTION_KEY],
                )
                await asyncio.sleep(0.1)

                await client.update_timer(
                    minutes=int(timer[MINUTES_KEY]),
                    delay_enabled=bool(timer[DELAY_KEY][ENABLED_KEY]),
                    delay_minutes=int(timer[DELAY_KEY][MINUTES_KEY]),
                    rpm=int(timer[RPM_KEY]),
                )
                await asyncio.sleep(0.1)

                if expected_voc_rpm is not None:
                    target_voc = target.data.modes["voc"]
                    await client.update_voc(
                        rpm=expected_voc_rpm,
                        humidity_dec_stop=int(
                            target_voc["humidity_dec_stop"]
                        ),
                        reserved=int(target_voc["reserved"]),
                    )
                    await asyncio.sleep(0.1)

                # Read every written setting back from the destination SKY.
                await client.fetch_constant_speed()
                await client.fetch_airing()
                await client.fetch_humidity()
                await client.fetch_light_and_voc()
                await client.fetch_timer()
                if not target.old_software_version:
                    await client.fetch_voc()

                self._verify_copied_settings(
                    client.modes,
                    constant_speed=constant_speed,
                    airing=airing,
                    humidity=humidity,
                    light_and_voc=light_and_voc,
                    timer=timer,
                    expected_voc_rpm=expected_voc_rpm,
                )

                target.settings_refresh_needed = False
                target.async_set_updated_data(client)

        finally:
            try:
                if should_disconnect:
                    async with target.update_lock:
                        await client.disconnect()
            finally:
                target.copy_in_progress = False

    @staticmethod
    def _verify_copied_settings(
        destination_modes: dict[str, Any],
        *,
        constant_speed: dict[str, Any],
        airing: dict[str, Any],
        humidity: dict[str, Any],
        light_and_voc: dict[str, Any],
        timer: dict[str, Any],
        expected_voc_rpm: int | None,
    ) -> None:
        """Verify values read back from the destination SKY."""
        checks = (
            (
                "constant speed enabled",
                bool(destination_modes["constant_speed"][ENABLED_KEY]),
                bool(constant_speed[ENABLED_KEY]),
            ),
            (
                "constant speed rpm",
                int(destination_modes["constant_speed"][RPM_KEY]),
                int(constant_speed[RPM_KEY]),
            ),
            (
                "airing enabled",
                bool(destination_modes["airing"][ENABLED_KEY]),
                bool(airing[ENABLED_KEY]),
            ),
            (
                "airing minutes",
                int(destination_modes["airing"][MINUTES_KEY]),
                int(airing[MINUTES_KEY]),
            ),
            (
                "airing rpm",
                int(destination_modes["airing"][RPM_KEY]),
                int(airing[RPM_KEY]),
            ),
            (
                "humidity enabled",
                bool(destination_modes["humidity"][ENABLED_KEY]),
                bool(humidity[ENABLED_KEY]),
            ),
            (
                "humidity detection",
                destination_modes["humidity"][DETECTION_KEY],
                humidity[DETECTION_KEY],
            ),
            (
                "humidity rpm",
                int(destination_modes["humidity"][RPM_KEY]),
                int(humidity[RPM_KEY]),
            ),
            (
                "light enabled",
                bool(
                    destination_modes["light_and_voc"]["light"][ENABLED_KEY]
                ),
                bool(light_and_voc["light"][ENABLED_KEY]),
            ),
            (
                "light detection",
                destination_modes["light_and_voc"]["light"][DETECTION_KEY],
                light_and_voc["light"][DETECTION_KEY],
            ),
            (
                "VOC enabled",
                bool(
                    destination_modes["light_and_voc"]["voc"][ENABLED_KEY]
                ),
                bool(light_and_voc["voc"][ENABLED_KEY]),
            ),
            (
                "VOC detection",
                destination_modes["light_and_voc"]["voc"][DETECTION_KEY],
                light_and_voc["voc"][DETECTION_KEY],
            ),
            (
                "timer minutes",
                int(destination_modes["timer"][MINUTES_KEY]),
                int(timer[MINUTES_KEY]),
            ),
            (
                "timer delay enabled",
                bool(destination_modes["timer"][DELAY_KEY][ENABLED_KEY]),
                bool(timer[DELAY_KEY][ENABLED_KEY]),
            ),
            (
                "timer delay minutes",
                int(destination_modes["timer"][DELAY_KEY][MINUTES_KEY]),
                int(timer[DELAY_KEY][MINUTES_KEY]),
            ),
            (
                "timer rpm",
                int(destination_modes["timer"][RPM_KEY]),
                int(timer[RPM_KEY]),
            ),
        )

        for setting, actual, expected in checks:
            if actual != expected:
                raise HomeAssistantError(
                    f"Copy verification failed for {setting}: "
                    f"expected {expected}, got {actual}"
                )

        if (
            expected_voc_rpm is not None
            and int(destination_modes["voc"][RPM_KEY])
            != expected_voc_rpm
        ):
            raise HomeAssistantError(
                "Copy verification failed for VOC rpm: "
                f"expected {expected_voc_rpm}, got "
                f"{destination_modes['voc'][RPM_KEY]}"
            )



class FreshIntelliventSkyActionButton(
    CoordinatorEntity[DataUpdateCoordinator[Any]], ButtonEntity
):
    """Button used to start or cancel Boost and Pause."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: FreshIntelliVent,
        entity_description: ButtonEntityDescription,
        action: str,
        enabled: bool,
    ) -> None:
        """Initialize an action button."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._action = action
        self._enabled = enabled

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

    async def async_press(self) -> None:
        """Start or cancel Boost or Pause."""
        if self._action == "boost":
            await self._handle_boost()
            return

        await self._handle_pause()

    async def _handle_boost(self) -> None:
        """Start or cancel Boost."""
        if self._enabled:
            minutes = int(getattr(self.coordinator, "boost_minutes", 15))
            rpm = int(getattr(self.coordinator, "boost_rpm", 2400))
        else:
            minutes = 0
            rpm = 0

        self.coordinator.pending_updates[BOOST_UPDATE] = {
            MINUTES_KEY: minutes,
            RPM_KEY: rpm,
        }

        if self.coordinator.keep_connection:
            return

        await self.coordinator.async_request_refresh()
        await asyncio.sleep(3)
        await self.coordinator.async_request_refresh()
        await asyncio.sleep(10)
        await self.coordinator.async_request_refresh()

    async def _handle_pause(self) -> None:
        """Start or cancel Pause."""
        minutes = int(getattr(self.coordinator, "pause_minutes", 15))

        self.coordinator.pending_updates[PAUSE_UPDATE] = {
            ENABLED_KEY: self._enabled,
            MINUTES_KEY: minutes,
        }

        if not self.coordinator.keep_connection:
            await self.coordinator.async_request_refresh()