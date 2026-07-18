import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .fresh_intellivent import FreshIntelliVent

from .const import (
    AIRING_MODE_UPDATE,
    BOOST_UPDATE,
    CONSTANT_SPEED_UPDATE,
    DELAY_KEY,
    DETECTION_KEY,
    ENABLED_KEY,
    HUMIDITY_MODE_UPDATE,
    LIGHT_AND_VOC_MODE_UPDATE,
    MINUTES_KEY,
    PAUSE_UPDATE,
    RPM_KEY,
    TIMER_MODE_UPDATE,
    VOC_MODE_UPDATE    
)

MAX_PENDING_WRITES_PER_BATCH = 32
PENDING_WRITE_DELAY = 0.1
POST_WRITE_READ_DELAY = 0.3

_LOGGER = logging.getLogger(__name__)


class FetchAndUpdate:
    def __init__(self, coordinator, client: FreshIntelliVent):
        self._coordinator = coordinator
        self._client = client
        self._is_authenticated = True

    def _clear_pending_if_written(
        self,
        update_key: str,
        written_value: object,
    ) -> None:
        """Clear only the exact pending value that was just written."""
        if self._coordinator.pending_updates.get(update_key) is written_value:
            self._coordinator.pending_updates[update_key] = None

    async def update_all(
        self,
        settings_refresh_needed: bool = True,
    ) -> bool:
        """Apply pending writes and refresh settings when needed."""
        did_write = await self._write_pending_updates()

        if did_write:
            await asyncio.sleep(POST_WRITE_READ_DELAY)

        # Read all settings after a successful write, or when a previous
        # settings refresh still needs to be completed.
        if did_write or settings_refresh_needed:
            await self._fetch_all_settings()

        return did_write

    async def _write_pending_updates(self) -> bool:
        """Write pending settings as one batch before the final read-back."""
        did_write = False
        write_count = 0

        handlers = [
            (BOOST_UPDATE, self._update_boost),
            (PAUSE_UPDATE, self._update_pause),
            (AIRING_MODE_UPDATE, self._update_airing),
            (CONSTANT_SPEED_UPDATE, self._update_constant_speed),
            (HUMIDITY_MODE_UPDATE, self._update_humidity),
            (LIGHT_AND_VOC_MODE_UPDATE, self._update_light_and_voc),
            (TIMER_MODE_UPDATE, self._update_timer),
        ]
        if not self._coordinator.old_software_version:
            handlers.append((VOC_MODE_UPDATE, self._update_voc))

        while write_count < MAX_PENDING_WRITES_PER_BATCH:
            next_handler = next(
                (
                    handler
                    for update_key, handler in handlers
                    if self._coordinator.pending_updates.get(update_key)
                    is not None
                ),
                None,
            )

            if next_handler is None:
                break

            if did_write:
                await asyncio.sleep(PENDING_WRITE_DELAY)

            if not await next_handler():
                break

            did_write = True
            write_count += 1

        if write_count == MAX_PENDING_WRITES_PER_BATCH and any(
            self._coordinator.pending_updates.get(update_key) is not None
            for update_key, _handler in handlers
        ):
            _LOGGER.warning(
                "Pending write batch reached the limit of %s writes; "
                "remaining settings will be written in the next update",
                MAX_PENDING_WRITES_PER_BATCH,
            )

        return did_write

    async def _fetch_all_settings(self) -> None:
        """Read all persistent settings from SKY."""
        await self._client.fetch_airing()
        await self._client.fetch_constant_speed()
        await self._client.fetch_humidity()
        await self._client.fetch_light_and_voc()
        await self._client.fetch_timer()
        if not self._coordinator.old_software_version:
            await self._client.fetch_voc()
        await self._client.fetch_boost()

    async def _update_boost(self) -> bool:
        """Start or cancel Boost."""
        boost = self._coordinator.pending_updates.get(BOOST_UPDATE)

        if boost is None or self._is_authenticated is not True:
            return False

        seconds=int(boost[MINUTES_KEY]) * 60
        fan_speed = int(boost[RPM_KEY])
        
        await self._client.update_boost(seconds=seconds, fan_speed=fan_speed)
       

        self._clear_pending_if_written(BOOST_UPDATE, boost)
        return True

    async def _update_pause(self) -> bool:
        pause = self._coordinator.pending_updates.get(PAUSE_UPDATE)

        if pause is None or self._is_authenticated is not True:
            return False

        await self._client.update_pause(
            enabled=bool(pause[ENABLED_KEY]),
            minutes=int(pause[MINUTES_KEY]),
        )
        self._clear_pending_if_written(PAUSE_UPDATE, pause)
        return True

    async def _update_airing(self) -> bool:
        airing_mode = self._coordinator.pending_updates.get(AIRING_MODE_UPDATE)

        if airing_mode is None or self._is_authenticated is not True:
            return False

        await self._client.update_airing(
            enabled=bool(airing_mode[ENABLED_KEY]),
            minutes=int(airing_mode[MINUTES_KEY]),
            rpm=int(airing_mode[RPM_KEY]),
        )
        self._clear_pending_if_written(AIRING_MODE_UPDATE, airing_mode)
        return True

    async def _update_constant_speed(self) -> bool:
        constant_speed = self._coordinator.pending_updates.get(CONSTANT_SPEED_UPDATE)

        if constant_speed is None or self._is_authenticated is not True:
            return False

        await self._client.update_constant_speed(
            enabled=constant_speed[ENABLED_KEY],
            rpm=constant_speed[RPM_KEY],
        )
        self._clear_pending_if_written(CONSTANT_SPEED_UPDATE, constant_speed)
        return True

    async def _update_humidity(self) -> bool:
        humidity_mode = self._coordinator.pending_updates.get(HUMIDITY_MODE_UPDATE)

        if humidity_mode is None or self._is_authenticated is not True:
            return False

        await self._client.update_humidity(
            enabled=bool(humidity_mode[ENABLED_KEY]),
            detection=humidity_mode[DETECTION_KEY],
            rpm=int(humidity_mode[RPM_KEY]),
        )
        self._clear_pending_if_written(HUMIDITY_MODE_UPDATE, humidity_mode)
        return True

    async def _update_light_and_voc(self) -> bool:
        light_and_voc_mode = self._coordinator.pending_updates.get(LIGHT_AND_VOC_MODE_UPDATE)

        if light_and_voc_mode is None or self._is_authenticated is not True:
            return False

        light = "light_"
        voc = "voc_"

        await self._client.update_light_and_voc(
            light_enabled=bool(light_and_voc_mode[light + ENABLED_KEY]),
            light_detection=light_and_voc_mode[light + DETECTION_KEY],
            voc_enabled=bool(light_and_voc_mode[voc + ENABLED_KEY]),
            voc_detection=light_and_voc_mode[voc + DETECTION_KEY],
        )
        self._clear_pending_if_written(
            LIGHT_AND_VOC_MODE_UPDATE,
            light_and_voc_mode,
        )
        return True

    async def _update_timer(self) -> bool:
        """Update timer/presence settings."""
        timer_mode = self._coordinator.pending_updates.get(TIMER_MODE_UPDATE)

        if timer_mode is None or self._is_authenticated is not True:
            return False

        await self._client.update_timer(
            minutes=timer_mode[MINUTES_KEY],
            delay_enabled=timer_mode[DELAY_KEY][ENABLED_KEY],
            delay_minutes=timer_mode[DELAY_KEY][MINUTES_KEY],
            rpm=int(timer_mode[RPM_KEY]),
        )

        self._clear_pending_if_written(TIMER_MODE_UPDATE, timer_mode)
        return True
        
    async def _update_voc(self) -> bool:
        """Update VOC mode RPM while preserving page 5 companion fields."""
        voc_mode = self._coordinator.pending_updates.get(VOC_MODE_UPDATE)

        if voc_mode is None or self._is_authenticated is not True:
            return False

        await self._client.update_voc(
            rpm=int(voc_mode[RPM_KEY]),
            humidity_dec_stop=int(voc_mode["humidity_dec_stop"]),
            reserved=int(voc_mode["reserved"]),
        )

        self._clear_pending_if_written(VOC_MODE_UPDATE, voc_mode)
        return True