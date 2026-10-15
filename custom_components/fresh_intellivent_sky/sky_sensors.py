from struct import unpack
from typing import Any, Union

MODE_UNKNOWN = "Unknown"

_TRIGGER_MODES = {
    0: "None",
    1: "Humidity",
    2: "Presence",
    3: "Timer",
    4: "VOC",
    5: "Automatic cycle",
    6: "Pause",
    7: "Boost",
    8: "Motor test",
    9: "Humidity sinking",
    10: "Unknown",
    11: "Delayed start",
}

_MOTOR_SPEED_MODES = {
    0: "Off",
    1: "Constant",
    2: "Timer",
    3: "Humidity",
    4: "Automatic cycles",
    5: "VOC",
    6: "Boost / Special",
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
    active_trigger_name: Union[str, None]
    motor_speed_name: Union[str, None]    

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
        self.mode_raw = int(values[1])
        self.active_trigger = self.mode_raw & 0x0F
        self.motor_speed = (self.mode_raw >> 4) & 0x0F

        self.active_trigger_name = _TRIGGER_MODES.get(
            self.active_trigger, MODE_UNKNOWN
        )
        self.motor_speed_name = _MOTOR_SPEED_MODES.get(
            self.motor_speed, MODE_UNKNOWN
        )

        self.status = bool(self.flags)

        if self.mode_raw == 0:
            self.mode = "Off"
        elif self.active_trigger == 0:
            self.mode = "Constant speed"
        elif self.active_trigger == 2:
            self.mode = "Light"
        else:
            self.mode = self.active_trigger_name

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
            "active_trigger_name": self.active_trigger_name,
            "motor_speed_name": self.motor_speed_name,
            "humidity_raw": self.humidity_raw,
            "voc_raw": self.voc_raw,
            "light_raw": self.light_raw,
            "rpm": self.rpm,
            "reference_raw": self.reference_raw,
            "minimum_active": self.minimum_active,
            "temperature": self.temperature,
            "error": self.error,
        }