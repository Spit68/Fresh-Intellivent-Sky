"""Support for sensors."""
from __future__ import annotations

from datetime import timedelta
import math
import time
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    REVOLUTIONS_PER_MINUTE,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from .const import BOOST_REMAINING_KEY, DOMAIN, PAUSE_REMAINING_KEY

if TYPE_CHECKING:
    from .fresh_intellivent import FreshIntelliVent


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
            FreshIntelliventSkySensor(
                coordinator,
                coordinator.data,
                SensorEntityDescription(
                    device_class=SensorDeviceClass.TEMPERATURE,
                    key="temperature",
                    translation_key="temperature",
                    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
            ),
            FreshIntelliventSkySensor(
                coordinator,
                coordinator.data,
                SensorEntityDescription(
                    key="humidity_raw",
                    translation_key="humidity_raw",
                    state_class=SensorStateClass.MEASUREMENT,
                    entity_registry_enabled_default=False,
                ),
                EntityCategory.DIAGNOSTIC,
            ),
            FreshIntelliventSkySensor(
                coordinator,
                coordinator.data,
                SensorEntityDescription(
                    key="voc_raw",
                    translation_key="voc_raw",
                    state_class=SensorStateClass.MEASUREMENT,
                    entity_registry_enabled_default=False,
                ),
                EntityCategory.DIAGNOSTIC,
            ),
            FreshIntelliventSkySensor(
                coordinator,
                coordinator.data,
                SensorEntityDescription(
                    key="light_raw",
                    translation_key="light_raw",
                    state_class=SensorStateClass.MEASUREMENT,
                    entity_registry_enabled_default=False,
                ),
                EntityCategory.DIAGNOSTIC,
            ),
            FreshIntelliventSkySensor(
                coordinator,
                coordinator.data,
                SensorEntityDescription(
                    key="reference_raw",
                    translation_key="reference_raw",
                    state_class=SensorStateClass.MEASUREMENT,
                    entity_registry_enabled_default=False,
                ),
                EntityCategory.DIAGNOSTIC,
            ),
            FreshIntelliventSkySensor(
                coordinator,
                coordinator.data,
                SensorEntityDescription(
                    key="minimum_active",
                    translation_key="minimum_active",
                    state_class=SensorStateClass.MEASUREMENT,
                    entity_registry_enabled_default=False,
                ),
                EntityCategory.DIAGNOSTIC,
            ),
            FreshIntelliventSkySensor(
                coordinator,
                coordinator.data,
                SensorEntityDescription(
                    key="error",
                    translation_key="error",
                ),
                EntityCategory.DIAGNOSTIC,
            ),
            FreshIntelliventSkySensor(
                coordinator,
                coordinator.data,
                SensorEntityDescription(
                    key="sw_version",
                    translation_key="sw_version",
                    entity_registry_enabled_default=False,
                ),
                EntityCategory.DIAGNOSTIC,
            ),
            FreshIntelliventSkySensor(
                coordinator,
                coordinator.data,
                SensorEntityDescription(
                    key="hw_version",
                    translation_key="hw_version",
                    entity_registry_enabled_default=False,
                ),
                EntityCategory.DIAGNOSTIC,
            ),
            FreshIntelliventSkySensor(
                coordinator,
                coordinator.data,
                SensorEntityDescription(
                    key="rssi",
                    translation_key="rssi",
                    native_unit_of_measurement="dBm",
                    state_class=SensorStateClass.MEASUREMENT,
                ),
                EntityCategory.DIAGNOSTIC,
            ),
            FreshIntelliventSkySensor(
                coordinator,
                coordinator.data,
                SensorEntityDescription(
                    key="bluetooth_source",
                    translation_key="bluetooth_source",
                ),
                EntityCategory.DIAGNOSTIC,
            ),
            FreshIntelliventSkySensor(
                coordinator,
                coordinator.data,
                SensorEntityDescription(
                    key="connection_status",
                    translation_key="connection_status",
                ),
                EntityCategory.DIAGNOSTIC,
            ),            
            FreshIntelliventSkySensor(
                coordinator,
                coordinator.data,
                SensorEntityDescription(
                    key="last_successful_update",
                    translation_key="last_successful_update",
                ),
                EntityCategory.DIAGNOSTIC,
            ),            
            FreshIntelliventSkySensor(
                coordinator,
                coordinator.data,
                SensorEntityDescription(
                    key="rpm",
                    translation_key="rpm",
                    native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
            ),
            FreshIntelliventSkySensor(
                coordinator,
                coordinator.data,
                SensorEntityDescription(
                    key="airflow",
                    translation_key="airflow",
                    native_unit_of_measurement="m³/h",
                    state_class=SensorStateClass.MEASUREMENT,
                    suggested_display_precision=1,
                ),
            ),           
            FreshIntelliventSkySensor(
                coordinator,
                coordinator.data,
                SensorEntityDescription(
                    key="mode",
                    translation_key="mode",
                ),
            ),
            FreshIntelliventSkySensor(
                coordinator,
                coordinator.data,
                SensorEntityDescription(
                    key="mode_raw",
                    translation_key="mode_raw",
                    state_class=SensorStateClass.MEASUREMENT,
                    entity_registry_enabled_default=False,
                ),
                EntityCategory.DIAGNOSTIC,
            ),
            FreshIntelliventSkySensor(
                coordinator,
                coordinator.data,
                SensorEntityDescription(
                    key=BOOST_REMAINING_KEY,
                    translation_key="boost_remaining",
                    native_unit_of_measurement=UnitOfTime.SECONDS,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
            ),
            FreshIntelliventSkySensor(
                coordinator,
                coordinator.data,
                SensorEntityDescription(
                    key="error_status",
                    translation_key="error_status",
                ),
            ),
            FreshIntelliventSkySensor(
                coordinator,
                coordinator.data,
                SensorEntityDescription(
                    key=PAUSE_REMAINING_KEY,
                    translation_key="pause_remaining",
                    native_unit_of_measurement=UnitOfTime.SECONDS,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
            ),
        ]
    )


class FreshIntelliventSkySensor(
    CoordinatorEntity[DataUpdateCoordinator[Any]], SensorEntity
):
    """Fresh Intellivent sensors for the device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: FreshIntelliVent,
        entity_description: SensorEntityDescription,
        entity_category: EntityCategory | None = None,
    ) -> None:
        """Populate the entity with relevant data."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        name = f"{device.manufacturer} {device.name}"

        self._attr_unique_id = f"{device.manufacturer}_{name}_{entity_description.key}"
        self._attr_entity_category = entity_category
        self._boost_deadline: float | None = None
        self._boost_remaining = 0
        self._pause_deadline: float | None = None
        self._pause_remaining = 0
        self._pause_reported_minutes: int | None = None
        self._unsub_countdown_timer = None
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

    async def async_added_to_hass(self) -> None:
        """Start the local Boost or Pause countdown."""
        await super().async_added_to_hass()

        if self.entity_description.key == BOOST_REMAINING_KEY:
            self._sync_boost_countdown()
        elif self.entity_description.key == PAUSE_REMAINING_KEY:
            self._sync_pause_countdown()
        else:
            return

        self._unsub_countdown_timer = async_track_time_interval(
            self.hass,
            self._handle_countdown_tick,
            timedelta(seconds=1),
        )

    async def async_will_remove_from_hass(self) -> None:
        """Stop the local countdown."""
        if self._unsub_countdown_timer is not None:
            self._unsub_countdown_timer()
            self._unsub_countdown_timer = None

        await super().async_will_remove_from_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Synchronize local countdown after every device poll."""
        if self.entity_description.key == BOOST_REMAINING_KEY:
            self._sync_boost_countdown()
        elif self.entity_description.key == PAUSE_REMAINING_KEY:
            self._sync_pause_countdown()

        super()._handle_coordinator_update()

    def _sync_boost_countdown(self) -> None:
        """Synchronize the local Boost countdown with the device."""
        boost = self.coordinator.data.modes.get("boost")

        if not boost or not boost.get("active", False):
            self._boost_deadline = None
            self._boost_remaining = 0
            return

        remaining = max(0, int(boost.get("time_remaining", 0)))

        self._boost_remaining = remaining
        self._boost_deadline = time.monotonic() + remaining

    def _sync_pause_countdown(self) -> None:
        """Synchronize Pause only when the device reports a changed minute value."""
        pause = self.coordinator.data.modes.get("pause")

        if not pause or not pause.get("enabled", False):
            self._pause_reported_minutes = None
            self._pause_deadline = None
            self._pause_remaining = 0
            return

        reported_minutes = max(0, int(pause.get("minutes", 0)))

        if reported_minutes == self._pause_reported_minutes:
            return

        self._pause_reported_minutes = reported_minutes
        self._pause_remaining = reported_minutes * 60
        self._pause_deadline = time.monotonic() + self._pause_remaining

    @callback
    def _handle_countdown_tick(self, _now) -> None:
        """Update the displayed Boost or Pause countdown once per second."""
        if self.entity_description.key == BOOST_REMAINING_KEY:
            deadline = self._boost_deadline
            current_remaining = self._boost_remaining
        elif self.entity_description.key == PAUSE_REMAINING_KEY:
            deadline = self._pause_deadline
            current_remaining = self._pause_remaining
        else:
            return

        if deadline is None:
            if current_remaining != 0:
                if self.entity_description.key == BOOST_REMAINING_KEY:
                    self._boost_remaining = 0
                else:
                    self._pause_remaining = 0
                self.async_write_ha_state()
            return

        remaining = max(
            0,
            math.ceil(deadline - time.monotonic()),
        )

        if remaining == current_remaining:
            return

        if self.entity_description.key == BOOST_REMAINING_KEY:
            self._boost_remaining = remaining
            if remaining == 0:
                self._boost_deadline = None
        else:
            self._pause_remaining = remaining
            if remaining == 0:
                self._pause_deadline = None

        self.async_write_ha_state()

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        if self.entity_description.key == BOOST_REMAINING_KEY:
            return self._boost_remaining

        if self.entity_description.key == PAUSE_REMAINING_KEY:
            return self._pause_remaining

        if self.entity_description.key == "sw_version":
            return self.coordinator.data.sw_version

        if self.entity_description.key == "hw_version":
            return self.coordinator.data.hw_version
            
        if self.entity_description.key == "rssi":
            return self.coordinator.rssi

        if self.entity_description.key == "bluetooth_source":
            return self.coordinator.bluetooth_source  

        if self.entity_description.key == "connection_status":
            return self.coordinator.connection_status            

        if self.entity_description.key == "last_successful_update":
            if self.coordinator.last_successful_update is None:
                return None
            return dt_util.as_local(
                self.coordinator.last_successful_update
            ).strftime("%d-%m-%Y %H:%M:%S")         
            
        if self.entity_description.key == "error_status":
            raw = self.coordinator.error_status["raw"]

            error_states = {
                0x00: "no_error",
                0x01: "stm8_not_responding",
                0x02: "high_temperature",
                0x04: "motor_not_running",
                0x08: "touch_buttons",
            }

            return error_states.get(raw, f"0x{raw:02X}") 

        if self.entity_description.key == "airflow":
            rpm = self.coordinator.data.sensors.rpm

            max_airflow = {
                ("100_mm", "standard"): 115.0,
                ("125_mm", "standard"): 140.0,
                ("100_mm", "design"): 95.0,
                ("125_mm", "design"): 110.0,
            }.get(
                (
                    self.coordinator.duct_size,
                    self.coordinator.front_type,
                )
            )

            if max_airflow is None:
                return None

            return round((rpm / 2400) * max_airflow, 1)            

        return self.coordinator.data.sensors.as_dict()[
            self.entity_description.key
        ]