"""Config flow and subentry flow tests for ha_alarm_clock."""

from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.ha_alarm_clock.config_flow_handler.schemas import to_form_data
from custom_components.ha_alarm_clock.const import (
    CONF_ALARM_TIME,
    CONF_AUDIO_PLAYLIST,
    CONF_AUDIO_TARGETS,
    DOMAIN,
    MUSIC_ASSISTANT_DOMAIN,
    MUSIC_ASSISTANT_SERVICE_GET_LIBRARY,
    MUSIC_ASSISTANT_SERVICE_PLAY_MEDIA,
    SECTION_SOUND,
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


async def test_alarm_form_offers_music_assistant_playlists(
    hass: HomeAssistant,
    music_assistant_player: str,
) -> None:
    """With Music Assistant present, the sound section offers its playlists and stores the pick."""
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

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

    sound = result["data_schema"].schema[SECTION_SOUND]
    playlist_field = sound.schema.schema[CONF_AUDIO_PLAYLIST]
    assert playlist_field.config["options"] == [{"value": PLAYLIST_URI, "label": PLAYLIST_NAME}]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        to_form_data(
            {
                **ALARM_DATA,
                CONF_AUDIO_TARGETS: [music_assistant_player],
                CONF_AUDIO_PLAYLIST: PLAYLIST_URI,
            },
        ),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    subentry = next(iter(entry.subentries.values()))
    assert subentry.data[CONF_AUDIO_PLAYLIST] == PLAYLIST_URI


async def test_playlist_without_a_music_assistant_speaker_is_rejected(
    hass: HomeAssistant,
    music_assistant_player: str,
) -> None:
    """Picking a playlist with a speaker Music Assistant does not own fails the form."""
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

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        to_form_data(
            {
                **ALARM_DATA,
                CONF_AUDIO_TARGETS: ["media_player.plain_speaker"],
                CONF_AUDIO_PLAYLIST: PLAYLIST_URI,
            },
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "playlist_needs_music_assistant_player"}
    assert hass.config_entries.async_entries(DOMAIN) == []


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

    second = {**ALARM_DATA, CONF_NAME: "Weekend", CONF_ALARM_TIME: "09:30:00"}
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], to_form_data(second))
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(init_integration.subentries) == 2
    assert hass.states.get("sensor.sunrise_alarm_weekend_next_alarm") is not None


async def test_removing_an_alarm_removes_its_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Deleting a subentry drops its entities, which no longer cascade via a device."""
    result = await hass.config_entries.subentries.async_init(
        (init_integration.entry_id, SUBENTRY_TYPE_ALARM),
        context={"source": SOURCE_USER},
    )
    second = {**ALARM_DATA, CONF_NAME: "Weekend", CONF_ALARM_TIME: "09:30:00"}
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
