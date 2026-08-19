"""Checks on the audio settings of a submitted alarm."""

from typing import TYPE_CHECKING, Any

from custom_components.ha_alarm_clock.const import (
    CONF_AUDIO_MEDIA,
    CONF_AUDIO_PLAYLIST,
    CONF_AUDIO_TARGETS,
    CONF_AUDIO_USE_MUSIC_ASSISTANT,
)
from custom_components.ha_alarm_clock.utils.music_assistant import async_music_assistant_targets
from homeassistant.core import callback

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@callback
def async_validate_alarm_audio(hass: HomeAssistant, alarm: dict[str, Any]) -> dict[str, str]:
    """
    Return the errors to show on the alarm form, keyed the way the flows expect.

    Returns:
        An empty dict when the alarm can play what it was told to.

    """
    targets = alarm.get(CONF_AUDIO_TARGETS) or []
    playlist = alarm.get(CONF_AUDIO_PLAYLIST)
    music_assistant = bool(playlist) or bool(alarm.get(CONF_AUDIO_USE_MUSIC_ASSISTANT))

    if (music_assistant or alarm.get(CONF_AUDIO_MEDIA)) and not targets:
        return {"base": "sound_needs_speaker"}

    if music_assistant and not async_music_assistant_targets(hass, targets):
        return {"base": "playlist_needs_music_assistant_player"}

    return {}
