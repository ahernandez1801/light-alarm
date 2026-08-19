"""Checks on the audio settings of a submitted alarm."""

from typing import TYPE_CHECKING, Any

from custom_components.ha_alarm_clock.const import CONF_AUDIO_PLAYLIST, CONF_AUDIO_TARGETS
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
    playlist = alarm.get(CONF_AUDIO_PLAYLIST)
    targets = alarm.get(CONF_AUDIO_TARGETS) or []

    if playlist and not async_music_assistant_targets(hass, targets):
        return {"base": "playlist_needs_music_assistant_player"}

    return {}
