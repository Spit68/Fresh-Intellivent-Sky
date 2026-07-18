"""Python interface for Fresh Intellivent Sky bathroom ventilation fan."""

from __future__ import annotations

import asyncio
from typing import Any, Union
from uuid import UUID

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection

from . import characteristics
from . import helpers as h
from .parser import SkyModeParser
from .sky_sensors import SkySensors

class FreshIntelliVent:
    """Fresh Intellivent Sky device handler."""

    name: str | None
    manufacturer: str | None
    model = "Intellivent Sky"
    fw_version: str | None
    hw_version: str | None
    sw_version: str | None
    _client: BleakClient | None
    modes: dict[str, Any]
    sensors: SkySensors

    def __init__(self, ble_device: BLEDevice) -> None:
        self.parser = SkyModeParser()
        self.modes = {}
        self.sensors = SkySensors()

        self.address = ble_device.address
        self._ble_device = ble_device
        self._client: BleakClient | None = None

    @property
    def is_connected(self) -> bool:
        """Return whether the BLE client is currently connected."""
        return self._client is not None and self._client.is_connected

    def update_ble_device(self, ble_device: BLEDevice) -> None:
        """Update the BLEDevice reference used for future connections."""
        self._ble_device = ble_device
        self.address = ble_device.address

    async def connect(
        self, timeout: float = 30.0
    ) -> None:
        """Connect to the device if it is not already connected."""
        if self.is_connected:
            return

        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            finally:
                self._client = None

        self._client = await establish_connection(
            BleakClient,
            self._ble_device,
            self._ble_device.address,
        )

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        if self._client is None:
            return

        try:
            if self._client.is_connected:
                await self._client.disconnect()
        finally:
            self._client = None

    async def authenticate(
        self, authentication_code: Union[bytes, bytearray, str]
    ) -> None:
        """Authenticate with the device."""
        await self._write_characteristic(
            uuid=characteristics.AUTH, data=h.to_bytearray(authentication_code)
        )
        await asyncio.sleep(1)

    async def fetch_authentication_code(self) -> Union[bytes, bytearray]:
        """Fetch the authentication code from the device."""
        if self._client is None:
            raise FreshIntelliventError("Not connected")

        return await self._client.read_gatt_char(char_specifier=characteristics.AUTH)

    async def _read_characteristics(
        self, uuid: Union[str, UUID]
    ) -> Union[bytes, bytearray]:
        """Read a characteristic from the device."""
        if self._client is None:
            raise FreshIntelliventError("Not connected")

        try:
            value = await self._client.read_gatt_char(char_specifier=uuid)
            return value
        except asyncio.TimeoutError as exc:
            raise TimeoutError("Timeout on read") from exc
        except BleakError as exc:
            raise FreshIntelliventError("Failed to read") from exc

    async def _write_characteristic(
        self, uuid: Union[str, UUID], data: Union[bytes, bytearray]
    ) -> None:
        if self._client is None:
            raise FreshIntelliventError("Not connected")

        try:
            await self._client.write_gatt_char(
                char_specifier=uuid, data=data, response=True
            )
        except asyncio.TimeoutError as exc:
            raise TimeoutError("Timeout on write") from exc
        except BleakError as exc:
            raise FreshIntelliventError("Failed to write") from exc

    async def fetch_device_information(self) -> None:
        """Fetch device information from the device."""
        if self._client is None:
            raise FreshIntelliventError("Not connected")

        name = await self._client.read_gatt_char(
            char_specifier=characteristics.DEVICE_NAME
        )
        self.name = name.decode("utf-8").replace("\00", "").replace("\0", "")

        fw_version = await self._client.read_gatt_char(
            char_specifier=characteristics.FIRMWARE_VERSION
        )
        self.fw_version = fw_version.decode("utf-8")

        hw_version = await self._client.read_gatt_char(
            char_specifier=characteristics.HARDWARE_VERSION
        )
        self.hw_version = hw_version.decode("utf-8")

        sw_version = await self._client.read_gatt_char(
            char_specifier=characteristics.SOFTWARE_VERSION
        )
        self.sw_version = sw_version.decode("utf-8")

        manufacturer = await self._client.read_gatt_char(
            char_specifier=characteristics.MANUFACTURER_NAME
        )
        self.manufacturer = manufacturer.decode("utf-8")

    async def fetch_humidity(self) -> dict[str, Any]:
        """Fetch humidity from the device."""
        value = await self._read_characteristics(uuid=characteristics.HUMIDITY)
        humidity = self.parser.humidity_read(value=value)
        self.modes["humidity"] = humidity
        return humidity

    async def update_humidity(self, enabled: bool, detection: str, rpm: int) -> None:
        """Update humidity settings on the device."""
        value = self.parser.humidity_write(
            enabled=enabled, detection=detection, rpm=rpm
        )
        await self._write_characteristic(characteristics.HUMIDITY, value)
        self.modes["humidity"] = {
            "enabled": enabled,
            "detection": detection,
            "detection_raw": h.detection_string_as_int(detection),
            "rpm": rpm,
        }

    async def fetch_light_and_voc(self) -> dict[str, Union[bool, int]]:
        """Fetch light and VOC levels from the device."""
        value = await self._read_characteristics(uuid=characteristics.LIGHT_VOC)
        light_and_voc = self.parser.light_and_voc_read(value=value)
        self.modes["light_and_voc"] = light_and_voc
        return light_and_voc

    async def update_light_and_voc(
        self,
        light_enabled: bool,
        light_detection: str,
        voc_enabled: bool,
        voc_detection: str,
    ) -> None:
        """Update light and VOC settings on the device."""
        value = self.parser.light_and_voc_write(
            light_enabled=light_enabled,
            light_detection=light_detection,
            voc_enabled=voc_enabled,
            voc_detection=voc_detection,
        )
        await self._write_characteristic(characteristics.LIGHT_VOC, value)
        self.modes["light_and_voc"] = {
            "light": {
                "enabled": light_enabled,
                "detection": light_detection,
                "detection_raw": h.detection_string_as_int(light_detection),
            },
            "voc": {
                "enabled": voc_enabled,
                "detection": voc_detection,
                "detection_raw": h.detection_string_as_int(voc_detection),
            },
        }

    async def fetch_voc(self) -> dict[str, int]:
        """Fetch VOC mode RPM from special settings page 5."""
        await self._write_characteristic(
            characteristics.SPECIAL_SETTINGS,
            bytes([0x05]),
        )

        await asyncio.sleep(0.15)

        value = await self._read_characteristics(
            uuid=characteristics.SPECIAL_SETTINGS
        )

        voc = self.parser.voc_read(value=value)
        self.modes["voc"] = voc
        return voc

    async def update_voc(
        self,
        rpm: int,
        humidity_dec_stop: int,
        reserved: int,
    ) -> None:
        """Update VOC mode RPM on special settings page 5."""
        value = self.parser.voc_write(
            rpm=rpm,
            humidity_dec_stop=humidity_dec_stop,
            reserved=reserved,
        )

        await self._write_characteristic(characteristics.SPECIAL_SETTINGS, value)
        self.modes["voc"] = {
            "rpm": rpm,
            "humidity_dec_stop": humidity_dec_stop,
            "reserved": reserved,
        }

    async def fetch_constant_speed(self) -> dict[str, Union[bool, int]]:
        """Fetch constant speed settings from the device."""
        value = await self._read_characteristics(uuid=characteristics.CONSTANT_SPEED)
        constant_speed = self.parser.constant_speed_read(value=value)
        self.modes["constant_speed"] = constant_speed
        return constant_speed

    async def update_constant_speed(self, enabled: bool, rpm: int) -> None:
        """Update constant speed settings on the device."""
        value = self.parser.constant_speed_write(enabled=enabled, rpm=rpm)
        hex_value = value.hex()
        await self._write_characteristic(
            characteristics.CONSTANT_SPEED, bytearray.fromhex(hex_value)
        )
        self.modes["constant_speed"] = {"enabled": enabled, "rpm": rpm}

    async def fetch_timer(self) -> dict[str, Union[bool, int]]:
        """Fetch timer settings from the device."""
        value = await self._read_characteristics(uuid=characteristics.TIMER)
        timer = self.parser.timer_read(value=value)
        self.modes["timer"] = timer
        return timer

    async def update_timer(
        self, minutes: int, delay_enabled: bool, delay_minutes: int, rpm: int
    ) -> None:
        """Update timer settings on the device."""
        value = self.parser.timer_write(
            minutes=minutes,
            delay_enabled=delay_enabled,
            delay_minutes=delay_minutes,
            rpm=rpm,
        )
        await self._write_characteristic(characteristics.TIMER, value)
        self.modes["timer"] = {
            "delay": {"enabled": delay_enabled, "minutes": delay_minutes},
            "minutes": minutes,
            "rpm": rpm,
        }

    async def fetch_airing(self) -> dict[str, Union[bool, int]]:
        """Fetch airing settings from the device."""
        value = await self._read_characteristics(uuid=characteristics.AIRING)
        airing = self.parser.airing_read(value=value)
        self.modes["airing"] = airing
        return airing

    async def update_airing(self, enabled: bool, minutes: int, rpm: int) -> None:
        """Update airing settings on the device."""
        value = self.parser.airing_write(enabled=enabled, minutes=minutes, rpm=rpm)
        await self._write_characteristic(characteristics.AIRING, value)
        self.modes["airing"] = {
            "enabled": enabled,
            "minutes": minutes,
            "rpm": rpm,
        }

    async def fetch_pause(self) -> dict[str, Union[bool, int]]:
        """Fetch pause settings from the device."""
        value = await self._read_characteristics(uuid=characteristics.PAUSE)
        pause = self.parser.pause_read(value=value)

        self.modes["pause"] = pause
        return pause

    async def update_pause(self, enabled: bool, minutes: int) -> None:
        """Update pause settings on the device."""
        value = self.parser.pause_write(enabled=enabled, minutes=minutes)
        await self._write_characteristic(characteristics.PAUSE, value)
        self.modes["pause"] = {"enabled": enabled, "minutes": minutes}

    async def fetch_boost(self) -> dict[str, Union[bool, int]]:
        """Fetch boost settings from the device."""
        value = await self._read_characteristics(uuid=characteristics.BOOST)
        boost = self.parser.boost_read(value=value)
        self.modes["boost"] = boost
        return boost

    async def update_boost(self, seconds: int, fan_speed: int) -> None:
        """Start or cancel user Boost."""
        value = self.parser.boost_write(seconds=seconds, fan_speed=fan_speed)
        await self._write_characteristic(characteristics.BOOST, value)

    async def update_temporary_speed(self, enabled: bool, rpm: int) -> None:
        """Update temporary speed settings on the device."""
        value = self.parser.temporary_speed_write(enabled=enabled, rpm=rpm)
        await self._write_characteristic(characteristics.TEMPORARY_SPEED, value)

    async def fetch_sensor_data(self) -> SkySensors:
        """Fetch sensor data from the device."""
        data = await self._read_characteristics(uuid=characteristics.DEVICE_STATUS)
        self.sensors.parse_data(data)
        return self.sensors


class FreshIntelliventError(Exception):
    """Base exception for Fresh Intellivent errors."""