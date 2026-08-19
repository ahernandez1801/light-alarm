"""
Best-effort audio for a ringing alarm.

Sound is one layer of the wake-up, never its backbone: every media call here is wrapped,
and a speaker that is offline, gone, or mid-firmware-update costs the user the music but
never the ringing state, the notifications or the buttons.
"""

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from custom_components.ha_alarm_clock.const import (
    CONF_AUDIO_MEDIA,
    CONF_AUDIO_PLAYLIST,
    CONF_AUDIO_RADIO_MODE,
    CONF_AUDIO_TARGETS,
    CONF_AUDIO_USE_MUSIC_ASSISTANT,
    CONF_AUDIO_VOLUME_END,
    CONF_AUDIO_VOLUME_MINUTES,
    CONF_AUDIO_VOLUME_START,
    DEFAULT_AUDIO_VOLUME_END,
    DEFAULT_AUDIO_VOLUME_MINUTES,
    DEFAULT_AUDIO_VOLUME_START,
    LOGGER,
    MUSIC_ASSISTANT_DOMAIN,
    MUSIC_ASSISTANT_MEDIA_TYPE_PLAYLIST,
    MUSIC_ASSISTANT_MEDIA_TYPES,
    MUSIC_ASSISTANT_SERVICE_PLAY_MEDIA,
)
from custom_components.ha_alarm_clock.utils.music_assistant import async_music_assistant_targets
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_MEDIA_STOP, SERVICE_TURN_OFF, SERVICE_VOLUME_SET
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from custom_components.ha_alarm_clock.coordinator import SunriseAlarmDataUpdateCoordinator
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant

ATTR_MA_MEDIA_ID = "media_id"
ATTR_MA_MEDIA_TYPE = "media_type"
ATTR_MA_RADIO_MODE = "radio_mode"

VOLUME_RAMP_STEP_SECONDS = 10


class AlarmAudio:
    """Start, ramp and stop the audio of a ringing alarm."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: SunriseAlarmDataUpdateCoordinator,
    ) -> None:
        """Initialize the audio player."""
        self._hass = hass
        self._coordinator = coordinator
        self._ramps: dict[str, CALLBACK_TYPE] = {}

    async def async_start(self, subentry_id: str) -> None:
        """Set the starting volume, start playback, and begin ramping the volume up."""
        config = self._async_config(subentry_id)
        targets = list(config.get(CONF_AUDIO_TARGETS, []))
        media = config.get(CONF_AUDIO_MEDIA)
        playlist = config.get(CONF_AUDIO_PLAYLIST)

        if not targets or not (media or playlist):
            return

        start = int(config.get(CONF_AUDIO_VOLUME_START, DEFAULT_AUDIO_VOLUME_START))
        end = int(config.get(CONF_AUDIO_VOLUME_END, DEFAULT_AUDIO_VOLUME_END))
        minutes = int(config.get(CONF_AUDIO_VOLUME_MINUTES, DEFAULT_AUDIO_VOLUME_MINUTES))

        await self._async_set_volume(targets, start)
        await self._async_play(targets, media, config)
        self._async_start_volume_ramp(subentry_id, targets, start, end, minutes)

    async def async_stop(self, subentry_id: str) -> None:
        """Stop playback and cancel the volume ramp for one alarm."""
        self._async_cancel_ramp(subentry_id)

        targets = list(self._async_config(subentry_id).get(CONF_AUDIO_TARGETS, []))
        if not targets:
            return

        try:
            await self._hass.services.async_call(
                MEDIA_PLAYER_DOMAIN,
                SERVICE_MEDIA_STOP,
                {ATTR_ENTITY_ID: targets},
                blocking=True,
            )
        except HomeAssistantError:
            await self._async_call_media(SERVICE_TURN_OFF, {ATTR_ENTITY_ID: targets})

    @callback
    def async_shutdown(self) -> None:
        """Cancel every volume ramp timer, leaving the players as they are."""
        for cancel in self._ramps.values():
            cancel()
        self._ramps.clear()

    async def _async_play(
        self,
        targets: Sequence[str],
        media: dict[str, Any] | None,
        config: dict[str, Any],
    ) -> None:
        """Start playback through Music Assistant when configured and present, else plainly."""
        playlist = str(config.get(CONF_AUDIO_PLAYLIST) or "")
        use_music_assistant = bool(playlist) or bool(config.get(CONF_AUDIO_USE_MUSIC_ASSISTANT, False))
        music_assistant_available = self._hass.services.has_service(
            MUSIC_ASSISTANT_DOMAIN,
            MUSIC_ASSISTANT_SERVICE_PLAY_MEDIA,
        )

        if use_music_assistant and not music_assistant_available:
            LOGGER.warning(
                "Music Assistant is configured for this alarm but not available; "
                "falling back to media_player.play_media",
            )

        music_assistant_targets = (
            async_music_assistant_targets(self._hass, targets) if music_assistant_available else []
        )

        if use_music_assistant and music_assistant_available and not music_assistant_targets:
            LOGGER.warning(
                "None of the speakers of this alarm (%s) are Music Assistant players, and "
                "music_assistant.play_media only reaches its own players; pick the Music "
                "Assistant copy of the speaker in the alarm's Sound section",
                ", ".join(targets),
            )

        if playlist and music_assistant_targets:
            await self._async_play_music_assistant(
                music_assistant_targets,
                playlist,
                MUSIC_ASSISTANT_MEDIA_TYPE_PLAYLIST,
                config,
            )
            return

        content_id = (media or {}).get(ATTR_MEDIA_CONTENT_ID, "")
        content_type = (media or {}).get(ATTR_MEDIA_CONTENT_TYPE, "")
        if not content_id:
            return

        if use_music_assistant and music_assistant_targets:
            await self._async_play_music_assistant(music_assistant_targets, content_id, content_type, config)
            return

        await self._async_call_media(
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: list(targets),
                ATTR_MEDIA_CONTENT_ID: content_id,
                ATTR_MEDIA_CONTENT_TYPE: content_type,
            },
        )

    async def _async_play_music_assistant(
        self,
        targets: Sequence[str],
        media_id: str,
        media_type: str,
        config: dict[str, Any],
    ) -> None:
        """Start playback of one item through Music Assistant."""
        data = {
            ATTR_ENTITY_ID: list(targets),
            ATTR_MA_MEDIA_ID: media_id,
            ATTR_MA_RADIO_MODE: bool(config.get(CONF_AUDIO_RADIO_MODE, False)),
        }

        if media_type in MUSIC_ASSISTANT_MEDIA_TYPES:
            data[ATTR_MA_MEDIA_TYPE] = media_type

        await self._async_call(MUSIC_ASSISTANT_DOMAIN, MUSIC_ASSISTANT_SERVICE_PLAY_MEDIA, data)

    @callback
    def _async_start_volume_ramp(
        self,
        subentry_id: str,
        targets: Sequence[str],
        start: int,
        end: int,
        minutes: int,
    ) -> None:
        """
        Step the volume from its starting to its final percentage.

        `media_player` has no transition parameter, so this is a timer stepping every
        few seconds rather than one handed-off call like the light sunrise.
        """
        self._async_cancel_ramp(subentry_id)

        if minutes <= 0 or end == start:
            return

        started_at = dt_util.utcnow()
        total_seconds = minutes * 60

        async def _step(now: datetime) -> None:
            fraction = min((now - started_at).total_seconds() / total_seconds, 1.0)
            await self._async_set_volume(targets, round(start + (end - start) * fraction))

            if fraction >= 1.0:
                self._async_cancel_ramp(subentry_id)

        self._ramps[subentry_id] = async_track_time_interval(
            self._hass,
            _step,
            timedelta(seconds=VOLUME_RAMP_STEP_SECONDS),
        )

    async def _async_set_volume(self, targets: Sequence[str], percent: int) -> None:
        """Set every target to one volume percentage."""
        await self._async_call_media(
            SERVICE_VOLUME_SET,
            {ATTR_ENTITY_ID: list(targets), ATTR_MEDIA_VOLUME_LEVEL: percent / 100},
        )

    async def _async_call_media(self, service: str, data: dict[str, Any]) -> None:
        """Call one media_player service, treating its failure as non-fatal."""
        await self._async_call(MEDIA_PLAYER_DOMAIN, service, data)

    async def _async_call(self, domain: str, service: str, data: dict[str, Any]) -> None:
        """Call one service, treating its failure as non-fatal."""
        try:
            await self._hass.services.async_call(domain, service, data, blocking=True)
        except (HomeAssistantError, vol.Invalid) as exception:
            LOGGER.warning("Could not call %s.%s for the alarm audio: %s", domain, service, exception)

    @callback
    def _async_config(self, subentry_id: str) -> dict[str, Any]:
        """
        Return the audio configuration of one alarm.

        Returns:
            The subentry data, or an empty dict when the subentry has been deleted.

        """
        subentry = self._coordinator.config_entry.subentries.get(subentry_id)
        return dict(subentry.data) if subentry is not None else {}

    @callback
    def _async_cancel_ramp(self, subentry_id: str) -> None:
        """Cancel the volume ramp timer for one alarm, if there is one."""
        cancel = self._ramps.pop(subentry_id, None)
        if cancel is not None:
            cancel()
