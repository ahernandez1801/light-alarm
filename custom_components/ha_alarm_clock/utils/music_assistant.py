"""
Which of an alarm's speakers Music Assistant can actually reach.

`music_assistant.play_media` is registered as a platform entity service, so it only ever
acts on the media players Music Assistant itself created. Targeting the Sonos or Chromecast
copy of the same speaker matches no entity, and Home Assistant answers with a log line
rather than an error — playback simply never starts.
"""

from typing import TYPE_CHECKING

from custom_components.ha_alarm_clock.const import MUSIC_ASSISTANT_DOMAIN
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

if TYPE_CHECKING:
    from collections.abc import Sequence

    from homeassistant.core import HomeAssistant


@callback
def async_music_assistant_targets(hass: HomeAssistant, targets: Sequence[str]) -> list[str]:
    """
    Return the entities among `targets` that the Music Assistant integration owns.

    Returns:
        The subset of targets `music_assistant.play_media` can act on.

    """
    registry = er.async_get(hass)

    return [
        entity_id
        for entity_id in targets
        if (entry := registry.async_get(entity_id)) is not None and entry.platform == MUSIC_ASSISTANT_DOMAIN
    ]
