from struct import unpack
from typing import Any, Union

MODE_UNKNOWN = "Unknown"

_MODES = {
    0: "Off",
    6: "Pause",
    16: "Constant speed",
    34: "Light",
    35: "Timer",
    49: "Humidity",
    84: "VOC",
    103: "Boost",
}

class SkySensors:
    """Sensor data container for Fresh Intellivent devices."""

    mode: Union[str, None]
    mode_raw: Union[int, None]
    status: Union[bool, None]
    raw_ble_payload: Union[str, None]
    flags: Union[int, None]
    active_trigger: Union[int, None]
    motor_speed: Union[int, None]

    humidity_raw: Union[int, None]
    voc_raw: Union[int, None]
    light_raw: Union[int, None]
    rpm: Union[int, None]
    reference_raw: Union[int, None]
    minimum_active: Union[int, None]
    temperature: Union[float, None]
    error: Union[int, None]

    def parse_data(self, data: Union[bytes, bytearray]) -> None:
        """Parse raw sensor data from the device."""
        if data is None:
            raise ValueError("Data cannot be None.")

        if len(data) != 15:
            raise ValueError(
                f"Length needs to be exactly 15 bytes, was {len(data)}."
            )

        values = unpack("<2B5H3B", data)
        
        self.raw_ble_payload = data.hex()
        self.flags = int(values[0])
        self.active_trigger = int(values[1] & 0x0F)
        self.motor_speed = int(values[1] >> 4)

        self.status = bool(self.flags)

        self.mode_raw = int(values[1])
        if mode := _MODES.get(self.mode_raw):
            self.mode = mode
        else:
            self.mode = MODE_UNKNOWN

        self.humidity_raw = values[2]
        self.voc_raw = values[3]
        self.light_raw = values[4]
        self.rpm = values[5]
        self.reference_raw = values[6]
        self.minimum_active = values[7]
        self.temperature = values[8]
        self.error = values[9]

    def as_dict(self) -> dict[str, Any]:
        """Return sensor data as a dictionary."""
        return {
            "status": self.status,
            "mode": self.mode,
            "mode_raw": self.mode_raw,
            "raw_ble_payload": self.raw_ble_payload,
            "flags": self.flags,
            "active_trigger": self.active_trigger,
            "motor_speed": self.motor_speed,
            "humidity_raw": self.humidity_raw,
            "voc_raw": self.voc_raw,
            "light_raw": self.light_raw,
            "rpm": self.rpm,
            "reference_raw": self.reference_raw,
            "minimum_active": self.minimum_active,
            "temperature": self.temperature,
            "error": self.error,
        }