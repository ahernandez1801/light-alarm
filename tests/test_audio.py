"""Audio tests for ha_alarm_clock — playback at the ring, the volume ramp, and stopping."""

from typing import Any

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.ha_alarm_clock.const import (
    CONF_AUDIO_MEDIA,
    CONF_AUDIO_PLAYLIST,
    CONF_AUDIO_RADIO_MODE,
    CONF_AUDIO_TARGETS,
    CONF_AUDIO_USE_MUSIC_ASSISTANT,
    CONF_AUDIO_VOLUME_END,
    CONF_AUDIO_VOLUME_MINUTES,
    CONF_AUDIO_VOLUME_START,
    MUSIC_ASSISTANT_DOMAIN,
    MUSIC_ASSISTANT_MEDIA_TYPE_PLAYLIST,
    MUSIC_ASSISTANT_SERVICE_PLAY_MEDIA,
)
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_SET,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from .conftest import AlarmCycle, AlarmEntities

AUDIO_TARGET = "media_player.bedroom"
AUDIO_MEDIA = {
    ATTR_MEDIA_CONTENT_ID: "media-source://media_source/local/wake.mp3",
    ATTR_MEDIA_CONTENT_TYPE: "music",
}
AUDIO_PLAYLIST = "library://playlist/12"

VOLUME_STEP_SECONDS = 60


@pytest.fixture
def audio_data(alarm_data: dict[str, Any]) -> dict[str, Any]:
    """
    Return an alarm configured to play through one speaker.

    Returns:
        The alarm configuration with audio settings added.

    """
    return {
        **alarm_data,
        CONF_AUDIO_TARGETS: [AUDIO_TARGET],
        CONF_AUDIO_MEDIA: AUDIO_MEDIA,
        CONF_AUDIO_VOLUME_START: 20,
        CONF_AUDIO_VOLUME_END: 60,
        CONF_AUDIO_VOLUME_MINUTES: 2,
    }


async def test_ring_sets_volume_then_plays(
    hass: HomeAssistant,
    audio_data: dict[str, Any],
    setup_with_data: Any,
    cycle: AlarmCycle,
) -> None:
    """At the ring, the speakers get the starting volume and then the chosen media."""
    async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_ON)
    volume_set = async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_VOLUME_SET)
    play_media = async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA)

    await setup_with_data(audio_data)
    await cycle.reach_ringing()

    assert len(volume_set) == 1
    assert volume_set[0].data[ATTR_ENTITY_ID] == [AUDIO_TARGET]
    assert volume_set[0].data[ATTR_MEDIA_VOLUME_LEVEL] == 0.2

    assert len(play_media) == 1
    assert play_media[0].data[ATTR_ENTITY_ID] == [AUDIO_TARGET]
    assert play_media[0].data[ATTR_MEDIA_CONTENT_ID] == AUDIO_MEDIA[ATTR_MEDIA_CONTENT_ID]
    assert play_media[0].data[ATTR_MEDIA_CONTENT_TYPE] == AUDIO_MEDIA[ATTR_MEDIA_CONTENT_TYPE]


async def test_music_assistant_path(
    hass: HomeAssistant,
    audio_data: dict[str, Any],
    setup_with_data: Any,
    cycle: AlarmCycle,
) -> None:
    """With Music Assistant configured and present, playback goes through it."""
    async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_ON)
    async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_VOLUME_SET)
    play_media = async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA)
    ma_play = async_mock_service(hass, MUSIC_ASSISTANT_DOMAIN, MUSIC_ASSISTANT_SERVICE_PLAY_MEDIA)

    await setup_with_data(
        {**audio_data, CONF_AUDIO_USE_MUSIC_ASSISTANT: True, CONF_AUDIO_RADIO_MODE: True},
    )
    await cycle.reach_ringing()

    assert play_media == []
    assert len(ma_play) == 1
    assert ma_play[0].data[ATTR_ENTITY_ID] == [AUDIO_TARGET]
    assert ma_play[0].data["media_id"] == AUDIO_MEDIA[ATTR_MEDIA_CONTENT_ID]
    assert ma_play[0].data["media_type"] == AUDIO_MEDIA[ATTR_MEDIA_CONTENT_TYPE]
    assert ma_play[0].data["radio_mode"] is True


async def test_playlist_plays_through_music_assistant(
    hass: HomeAssistant,
    audio_data: dict[str, Any],
    setup_with_data: Any,
    cycle: AlarmCycle,
) -> None:
    """A chosen playlist plays through Music Assistant, even without the toggle or a media pick."""
    async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_ON)
    async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_VOLUME_SET)
    play_media = async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA)
    ma_play = async_mock_service(hass, MUSIC_ASSISTANT_DOMAIN, MUSIC_ASSISTANT_SERVICE_PLAY_MEDIA)

    playlist_only = {**audio_data, CONF_AUDIO_PLAYLIST: AUDIO_PLAYLIST}
    del playlist_only[CONF_AUDIO_MEDIA]
    await setup_with_data(playlist_only)
    await cycle.reach_ringing()

    assert play_media == []
    assert len(ma_play) == 1
    assert ma_play[0].data[ATTR_ENTITY_ID] == [AUDIO_TARGET]
    assert ma_play[0].data["media_id"] == AUDIO_PLAYLIST
    assert ma_play[0].data["media_type"] == MUSIC_ASSISTANT_MEDIA_TYPE_PLAYLIST


async def test_playlist_without_music_assistant_falls_back(
    hass: HomeAssistant,
    audio_data: dict[str, Any],
    setup_with_data: Any,
    cycle: AlarmCycle,
) -> None:
    """When Music Assistant is gone, the alarm falls back to the plain media pick."""
    async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_ON)
    async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_VOLUME_SET)
    play_media = async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA)

    await setup_with_data({**audio_data, CONF_AUDIO_PLAYLIST: AUDIO_PLAYLIST})
    await cycle.reach_ringing()

    assert len(play_media) == 1
    assert play_media[0].data[ATTR_MEDIA_CONTENT_ID] == AUDIO_MEDIA[ATTR_MEDIA_CONTENT_ID]


async def test_music_assistant_absent_falls_back(
    hass: HomeAssistant,
    audio_data: dict[str, Any],
    setup_with_data: Any,
    cycle: AlarmCycle,
) -> None:
    """An alarm configured for a removed Music Assistant still plays plainly."""
    async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_ON)
    async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_VOLUME_SET)
    play_media = async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA)

    await setup_with_data({**audio_data, CONF_AUDIO_USE_MUSIC_ASSISTANT: True})
    await cycle.reach_ringing()

    assert len(play_media) == 1
    assert play_media[0].data[ATTR_MEDIA_CONTENT_ID] == AUDIO_MEDIA[ATTR_MEDIA_CONTENT_ID]


async def test_volume_ramps_to_the_final_level(
    hass: HomeAssistant,
    audio_data: dict[str, Any],
    setup_with_data: Any,
    cycle: AlarmCycle,
) -> None:
    """The volume steps up from the starting to the final percentage, then stops."""
    async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_ON)
    volume_set = async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_VOLUME_SET)
    async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA)

    await setup_with_data(audio_data)
    await cycle.reach_ringing()

    await cycle.advance(VOLUME_STEP_SECONDS)
    assert volume_set[-1].data[ATTR_MEDIA_VOLUME_LEVEL] == 0.4

    await cycle.advance(VOLUME_STEP_SECONDS)
    assert volume_set[-1].data[ATTR_MEDIA_VOLUME_LEVEL] == 0.6

    calls_after_ramp = len(volume_set)
    await cycle.advance(VOLUME_STEP_SECONDS)
    assert len(volume_set) == calls_after_ramp


async def test_snooze_stops_the_audio(
    hass: HomeAssistant,
    audio_data: dict[str, Any],
    setup_with_data: Any,
    cycle: AlarmCycle,
    entities: AlarmEntities,
) -> None:
    """A snooze stops playback and its volume ramp."""
    async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_ON)
    async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_OFF)
    volume_set = async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_VOLUME_SET)
    async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA)
    media_stop = async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_MEDIA_STOP)

    await setup_with_data(audio_data)
    await cycle.reach_ringing()
    await cycle.press(entities.snooze)

    assert len(media_stop) == 1
    assert media_stop[0].data[ATTR_ENTITY_ID] == [AUDIO_TARGET]

    calls_after_stop = len(volume_set)
    await cycle.advance(VOLUME_STEP_SECONDS)
    assert len(volume_set) == calls_after_stop


async def test_dismiss_stops_the_audio(
    hass: HomeAssistant,
    audio_data: dict[str, Any],
    setup_with_data: Any,
    cycle: AlarmCycle,
    entities: AlarmEntities,
) -> None:
    """Dismissing stops playback while the lights stay on."""
    async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_ON)
    media_stop = async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_MEDIA_STOP)
    async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_VOLUME_SET)
    async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA)

    await setup_with_data(audio_data)
    await cycle.reach_ringing()
    await cycle.press(entities.dismiss)

    assert len(media_stop) == 1


async def test_media_stop_falls_back_to_turn_off(
    hass: HomeAssistant,
    audio_data: dict[str, Any],
    setup_with_data: Any,
    cycle: AlarmCycle,
    entities: AlarmEntities,
) -> None:
    """A player that cannot stop is turned off instead."""
    async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_ON)
    async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_VOLUME_SET)
    async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA)
    turn_off = async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_TURN_OFF)

    async def _reject(_call: ServiceCall) -> None:
        raise HomeAssistantError("stop is not supported")

    hass.services.async_register(MEDIA_PLAYER_DOMAIN, SERVICE_MEDIA_STOP, _reject)

    await setup_with_data(audio_data)
    await cycle.reach_ringing()
    await cycle.press(entities.dismiss)

    assert len(turn_off) == 1
    assert turn_off[0].data[ATTR_ENTITY_ID] == [AUDIO_TARGET]


async def test_audio_failure_does_not_stop_the_ring(
    hass: HomeAssistant,
    audio_data: dict[str, Any],
    setup_with_data: Any,
    cycle: AlarmCycle,
    entities: AlarmEntities,
) -> None:
    """A failing player costs the sound, never the ringing state."""
    async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_ON)
    async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_VOLUME_SET)

    async def _reject(_call: ServiceCall) -> None:
        raise HomeAssistantError("player unavailable")

    hass.services.async_register(MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA, _reject)

    await setup_with_data(audio_data)
    await cycle.reach_ringing()

    assert hass.states.get(entities.ringing).state == STATE_ON


async def test_no_audio_configured_stays_silent(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    cycle: AlarmCycle,
    entities: AlarmEntities,
) -> None:
    """An alarm without speakers rings without any media call."""
    async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_ON)
    volume_set = async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_VOLUME_SET)
    play_media = async_mock_service(hass, MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA)

    await cycle.reach_ringing()

    assert volume_set == []
    assert play_media == []
    assert hass.states.get(entities.ringing).state == STATE_ON
