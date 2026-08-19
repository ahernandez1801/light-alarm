"""Config flow and subentry flow tests for ha_alarm_clock."""

from typing import Any

from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.ha_alarm_clock.config_flow_handler.schemas import to_form_data
from custom_components.ha_alarm_clock.const import (
    AUDIO_MODE_MUSIC_ASSISTANT,
    AUDIO_MODE_NONE,
    AUDIO_MODE_SPEAKER,
    CONF_ALARM_TIME,
    CONF_AUDIO_MODE,
    CONF_AUDIO_PLAYLIST,
    CONF_AUDIO_TARGETS,
    CONF_AUDIO_USE_MUSIC_ASSISTANT,
    DOMAIN,
    MUSIC_ASSISTANT_DOMAIN,
    MUSIC_ASSISTANT_SERVICE_GET_LIBRARY,
    MUSIC_ASSISTANT_SERVICE_PLAY_MEDIA,
    SUBENTRY_TYPE_ALARM,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from .conftest import ALARM_DATA, ALARM_NAME

PLAYLIST_URI = "library://playlist/12"
PLAYLIST_NAME = "Morning"


def _mock_music_assistant(hass: HomeAssistant) -> None:
    """Register a loaded Music Assistant entry with one library playlist."""
    music_assistant = MockConfigEntry(domain=MUSIC_ASSISTANT_DOMAIN)
    music_assistant.add_to_hass(hass)
    music_assistant.mock_state(hass, ConfigEntryState.LOADED)
    async_mock_service(hass, MUSIC_ASSISTANT_DOMAIN, MUSIC_ASSISTANT_SERVICE_PLAY_MEDIA)
    async_mock_service(
        hass,
        MUSIC_ASSISTANT_DOMAIN,
        MUSIC_ASSISTANT_SERVICE_GET_LIBRARY,
        response={"items": [{"name": PLAYLIST_NAME, "uri": PLAYLIST_URI, "media_type": "playlist"}]},
        supports_response=SupportsResponse.ONLY,
    )


async def test_user_flow_creates_entry_with_first_alarm(hass: HomeAssistant) -> None:
    """The setup dialog collects one alarm and stores it as the entry's first subentry."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], to_form_data(ALARM_DATA))
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {}

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    subentry = next(iter(entry.subentries.values()))
    assert subentry.subentry_type == SUBENTRY_TYPE_ALARM
    assert subentry.title == ALARM_NAME
    assert subentry.data[CONF_ALARM_TIME] == ALARM_DATA[CONF_ALARM_TIME]
    assert CONF_AUDIO_MODE not in subentry.data


async def test_sound_mode_hides_music_assistant_when_absent(hass: HomeAssistant) -> None:
    """Without Music Assistant installed, the sound choice does not offer it."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

    mode_field = result["data_schema"].schema[CONF_AUDIO_MODE]
    assert mode_field.config["options"] == [AUDIO_MODE_NONE, AUDIO_MODE_SPEAKER]


async def test_music_assistant_step_offers_only_its_playlists_and_players(
    hass: HomeAssistant,
    music_assistant_player: str,
) -> None:
    """The Music Assistant sound step offers its playlists and only its own speakers."""
    _mock_music_assistant(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    mode_field = result["data_schema"].schema[CONF_AUDIO_MODE]
    assert AUDIO_MODE_MUSIC_ASSISTANT in mode_field.config["options"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        to_form_data({**ALARM_DATA, CONF_AUDIO_MODE: AUDIO_MODE_MUSIC_ASSISTANT}),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sound"

    schema = result["data_schema"].schema
    playlist_field = schema[CONF_AUDIO_PLAYLIST]
    assert playlist_field.config["options"] == [{"value": PLAYLIST_URI, "label": PLAYLIST_NAME}]

    targets_field = schema[CONF_AUDIO_TARGETS]
    assert targets_field.config["integration"] == MUSIC_ASSISTANT_DOMAIN
    assert "audio_media" not in {str(key) for key in schema}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_AUDIO_PLAYLIST: PLAYLIST_URI, CONF_AUDIO_TARGETS: [music_assistant_player]},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    subentry = next(iter(entry.subentries.values()))
    assert subentry.data[CONF_AUDIO_PLAYLIST] == PLAYLIST_URI
    assert subentry.data[CONF_AUDIO_TARGETS] == [music_assistant_player]
    assert subentry.data[CONF_AUDIO_USE_MUSIC_ASSISTANT] is True


async def test_playlist_without_a_music_assistant_speaker_is_rejected(
    hass: HomeAssistant,
    music_assistant_player: str,
) -> None:
    """Submitting a speaker Music Assistant does not own fails the sound step."""
    _mock_music_assistant(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        to_form_data({**ALARM_DATA, CONF_AUDIO_MODE: AUDIO_MODE_MUSIC_ASSISTANT}),
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_AUDIO_PLAYLIST: PLAYLIST_URI, CONF_AUDIO_TARGETS: ["media_player.plain_speaker"]},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sound"
    assert result["errors"] == {"base": "playlist_needs_music_assistant_player"}
    assert hass.config_entries.async_entries(DOMAIN) == []


async def test_sound_step_requires_a_speaker(hass: HomeAssistant) -> None:
    """A sound mode without any speaker picked fails the sound step."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        to_form_data({**ALARM_DATA, CONF_AUDIO_MODE: AUDIO_MODE_SPEAKER}),
    )
    assert result["step_id"] == "sound"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_AUDIO_TARGETS: [],
            "audio_media": {
                "entity_id": "media_player.bedroom",
                "media_content_id": "media-source://media_source/local/wake.mp3",
                "media_content_type": "music",
            },
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "sound_needs_speaker"}


async def test_single_entry_only(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """A second setup attempt aborts, because alarms are added as subentries instead."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_subentry_flow_adds_second_alarm(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """The add-alarm dialog creates another subentry on the existing entry."""
    result = await hass.config_entries.subentries.async_init(
        (init_integration.entry_id, SUBENTRY_TYPE_ALARM),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM

    second: dict[str, Any] = {**ALARM_DATA, CONF_NAME: "Weekend", CONF_ALARM_TIME: "09:30:00"}
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], to_form_data(second))
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(init_integration.subentries) == 2
    assert hass.states.get("sensor.sunrise_alarm_weekend_next_alarm") is not None


async def test_reconfigure_reopens_the_sound_step_prefilled(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    music_assistant_player: str,
) -> None:
    """Editing a Music Assistant alarm derives its mode and prefills the sound step."""
    _mock_music_assistant(hass)

    result = await hass.config_entries.subentries.async_init(
        (init_integration.entry_id, SUBENTRY_TYPE_ALARM),
        context={"source": SOURCE_USER},
    )
    second: dict[str, Any] = {**ALARM_DATA, CONF_NAME: "Weekend", CONF_AUDIO_MODE: AUDIO_MODE_MUSIC_ASSISTANT}
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], to_form_data(second))
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_AUDIO_PLAYLIST: PLAYLIST_URI, CONF_AUDIO_TARGETS: [music_assistant_player]},
    )
    await hass.async_block_till_done()

    weekend = next(
        subentry_id for subentry_id, subentry in init_integration.subentries.items() if subentry.title == "Weekend"
    )

    result = await hass.config_entries.subentries.async_init(
        (init_integration.entry_id, SUBENTRY_TYPE_ALARM),
        context={"source": "reconfigure", "subentry_id": weekend},
    )
    assert result["step_id"] == "reconfigure"

    submitted = dict(init_integration.subentries[weekend].data)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        to_form_data({**submitted, CONF_NAME: "Weekend"}),
    )
    assert result["step_id"] == "sound"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_AUDIO_PLAYLIST: PLAYLIST_URI, CONF_AUDIO_TARGETS: [music_assistant_player]},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert init_integration.subentries[weekend].data[CONF_AUDIO_PLAYLIST] == PLAYLIST_URI


async def test_removing_an_alarm_removes_its_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Deleting a subentry drops its entities, which no longer cascade via a device."""
    result = await hass.config_entries.subentries.async_init(
        (init_integration.entry_id, SUBENTRY_TYPE_ALARM),
        context={"source": SOURCE_USER},
    )
    second: dict[str, Any] = {**ALARM_DATA, CONF_NAME: "Weekend", CONF_ALARM_TIME: "09:30:00"}
    await hass.config_entries.subentries.async_configure(result["flow_id"], to_form_data(second))
    await hass.async_block_till_done()

    weekend = next(
        subentry_id for subentry_id, subentry in init_integration.subentries.items() if subentry.title == "Weekend"
    )
    hass.config_entries.async_remove_subentry(init_integration, weekend)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.sunrise_alarm_weekend_next_alarm") is None
    assert er.async_get(hass).async_get("sensor.sunrise_alarm_weekend_next_alarm") is None
    assert hass.states.get("sensor.sunrise_alarm_weekday_next_alarm") is not None
