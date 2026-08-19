"""
Voluptuous schemas for the alarm dialog, shared by setup, add and reconfigure.

The dialog is two steps. The first collects the alarm itself and a choice of how it
sounds; the second collects the sound settings for that choice, so a Music Assistant
alarm is only ever offered Music Assistant speakers and its own library, never the
media browser that would hand back an unplayable `media-source://` id.
"""

import asyncio
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from custom_components.ha_alarm_clock.const import (
    AUDIO_MODE_MUSIC_ASSISTANT,
    AUDIO_MODE_NONE,
    AUDIO_MODE_SPEAKER,
    CONF_ALARM_TIME,
    CONF_AUDIO_MEDIA,
    CONF_AUDIO_MODE,
    CONF_AUDIO_PLAYLIST,
    CONF_AUDIO_RADIO_MODE,
    CONF_AUDIO_TARGETS,
    CONF_AUDIO_USE_MUSIC_ASSISTANT,
    CONF_AUDIO_VOLUME_END,
    CONF_AUDIO_VOLUME_MINUTES,
    CONF_AUDIO_VOLUME_START,
    CONF_GATE_ENTITY,
    CONF_GATE_STATE,
    CONF_LIGHTS,
    CONF_NOTIFY_TARGETS,
    CONF_PHONE_CRITICAL_SOUND,
    CONF_RAMP_MINUTES,
    CONF_SNOOZE_MINUTES,
    DEFAULT_AUDIO_VOLUME_END,
    DEFAULT_AUDIO_VOLUME_MINUTES,
    DEFAULT_AUDIO_VOLUME_START,
    DEFAULT_GATE_STATE,
    DEFAULT_RAMP_MINUTES,
    DEFAULT_SNOOZE_MINUTES,
    LOGGER,
    MAX_AUDIO_VOLUME_MINUTES,
    MAX_RAMP_MINUTES,
    MAX_SNOOZE_MINUTES,
    MUSIC_ASSISTANT_DOMAIN,
    MUSIC_ASSISTANT_MEDIA_TYPE_PLAYLIST,
    MUSIC_ASSISTANT_SERVICE_GET_LIBRARY,
    MUSIC_ASSISTANT_SERVICE_PLAY_MEDIA,
    NOTIFY_DOMAIN,
    NOTIFY_SERVICE_PREFIX,
    SECTION_ADVANCED,
)
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME, PERCENTAGE
from homeassistant.data_entry_flow import section
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

DEFAULT_ALARM_TIME = "07:00:00"

ATTR_MA_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_MA_ITEMS = "items"
ATTR_MA_LIMIT = "limit"
ATTR_MA_MEDIA_TYPE = "media_type"
ATTR_MA_NAME = "name"
ATTR_MA_URI = "uri"

PLAYLIST_FETCH_LIMIT = 500
PLAYLIST_FETCH_TIMEOUT_SECONDS = 10

ADVANCED_KEYS = (
    CONF_RAMP_MINUTES,
    CONF_SNOOZE_MINUTES,
    CONF_NOTIFY_TARGETS,
    CONF_PHONE_CRITICAL_SOUND,
    CONF_GATE_ENTITY,
    CONF_GATE_STATE,
)
SOUND_KEYS = (
    CONF_AUDIO_TARGETS,
    CONF_AUDIO_MEDIA,
    CONF_AUDIO_PLAYLIST,
    CONF_AUDIO_USE_MUSIC_ASSISTANT,
    CONF_AUDIO_RADIO_MODE,
    CONF_AUDIO_VOLUME_START,
    CONF_AUDIO_VOLUME_END,
    CONF_AUDIO_VOLUME_MINUTES,
)
SECTIONS = (SECTION_ADVANCED,)


def async_get_alarm_schema(hass: HomeAssistant) -> vol.Schema:
    """
    Return the schema for the first step: the alarm itself and how it sounds.

    Name, time and lights are the whole dialog; the sound choice decides whether a
    second step follows, and everything with a sensible default sits in a collapsed
    section.

    Returns:
        The schema for the alarm form.

    """
    music_assistant = hass.services.has_service(MUSIC_ASSISTANT_DOMAIN, MUSIC_ASSISTANT_SERVICE_PLAY_MEDIA)
    modes = [AUDIO_MODE_NONE, AUDIO_MODE_SPEAKER]
    if music_assistant:
        modes.append(AUDIO_MODE_MUSIC_ASSISTANT)

    return vol.Schema(
        {
            vol.Required(CONF_NAME): selector.TextSelector(),
            vol.Required(CONF_ALARM_TIME, default=DEFAULT_ALARM_TIME): selector.TimeSelector(),
            vol.Required(CONF_LIGHTS): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=LIGHT_DOMAIN, multiple=True),
            ),
            vol.Required(CONF_AUDIO_MODE, default=AUDIO_MODE_NONE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=modes,
                    translation_key=CONF_AUDIO_MODE,
                    mode=selector.SelectSelectorMode.LIST,
                ),
            ),
            vol.Required(SECTION_ADVANCED): section(_advanced_schema(hass), {"collapsed": True}),
        },
    )


async def async_get_sound_schema(hass: HomeAssistant, mode: str) -> vol.Schema:
    """
    Return the schema for the second step: the sound settings of one mode.

    A Music Assistant alarm picks from its own playlists and is only offered the media
    players Music Assistant itself created, because `music_assistant.play_media` acts on
    no others. A plain speaker alarm browses media the way the media player would.

    Returns:
        The schema for the sound form.

    """
    fields: dict[Any, Any]

    if mode == AUDIO_MODE_MUSIC_ASSISTANT:
        fields = {
            vol.Required(CONF_AUDIO_PLAYLIST): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=await _async_music_assistant_playlists(hass),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    custom_value=True,
                    sort=True,
                ),
            ),
            vol.Required(CONF_AUDIO_TARGETS): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=MEDIA_PLAYER_DOMAIN,
                    integration=MUSIC_ASSISTANT_DOMAIN,
                    multiple=True,
                ),
            ),
            vol.Required(CONF_AUDIO_RADIO_MODE, default=False): selector.BooleanSelector(),
        }
    else:
        fields = {
            vol.Required(CONF_AUDIO_TARGETS): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=MEDIA_PLAYER_DOMAIN, multiple=True),
            ),
            vol.Required(CONF_AUDIO_MEDIA): selector.MediaSelector(),
        }

    fields.update(
        {
            vol.Required(CONF_AUDIO_VOLUME_START, default=DEFAULT_AUDIO_VOLUME_START): _percentage_selector(),
            vol.Required(CONF_AUDIO_VOLUME_END, default=DEFAULT_AUDIO_VOLUME_END): _percentage_selector(),
            vol.Required(CONF_AUDIO_VOLUME_MINUTES, default=DEFAULT_AUDIO_VOLUME_MINUTES): _minutes_selector(
                MAX_AUDIO_VOLUME_MINUTES,
                minimum=0,
            ),
        },
    )

    return vol.Schema(fields)


def flatten_alarm_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """
    Fold the collapsed sections back into a flat alarm configuration.

    Returns:
        The submitted values with every section's keys at the top level.

    """
    flattened = {key: value for key, value in user_input.items() if key not in SECTIONS}
    for name in SECTIONS:
        flattened.update(user_input.get(name, {}))

    return flattened


def merge_alarm(main: dict[str, Any], sound: dict[str, Any] | None) -> dict[str, Any]:
    """
    Combine the two steps into the alarm configuration that gets stored.

    The mode itself is not stored — it is derived from what is — and the keys of the
    modes not chosen are dropped, so switching an alarm from Music Assistant to a plain
    speaker leaves no stale playlist behind.

    Returns:
        The flat alarm configuration.

    """
    mode = main.get(CONF_AUDIO_MODE, AUDIO_MODE_NONE)
    alarm = {key: value for key, value in flatten_alarm_input(main).items() if key != CONF_AUDIO_MODE}

    if mode == AUDIO_MODE_NONE or not sound:
        return alarm

    alarm.update(sound)
    alarm[CONF_AUDIO_USE_MUSIC_ASSISTANT] = mode == AUDIO_MODE_MUSIC_ASSISTANT

    if mode == AUDIO_MODE_MUSIC_ASSISTANT:
        alarm.pop(CONF_AUDIO_MEDIA, None)
    else:
        alarm.pop(CONF_AUDIO_PLAYLIST, None)
        alarm.pop(CONF_AUDIO_RADIO_MODE, None)

    return alarm


def audio_mode_of(data: dict[str, Any]) -> str:
    """
    Derive the sound mode of a stored alarm.

    Returns:
        The mode the sound step of a reconfigure should open in.

    """
    if data.get(CONF_AUDIO_PLAYLIST) or data.get(CONF_AUDIO_USE_MUSIC_ASSISTANT):
        return AUDIO_MODE_MUSIC_ASSISTANT

    if data.get(CONF_AUDIO_TARGETS):
        return AUDIO_MODE_SPEAKER

    return AUDIO_MODE_NONE


def to_form_data(data: dict[str, Any]) -> dict[str, Any]:
    """
    Shape a stored alarm the way the first step's form expects it.

    Returns:
        The alarm configuration with the advanced keys nested in their section and the
        derived sound mode filled in.

    """
    nested_keys = ADVANCED_KEYS + SOUND_KEYS
    return {
        **{key: value for key, value in data.items() if key not in nested_keys},
        CONF_AUDIO_MODE: data.get(CONF_AUDIO_MODE, audio_mode_of(data)),
        SECTION_ADVANCED: {key: data[key] for key in ADVANCED_KEYS if key in data},
    }


def to_sound_form_data(data: dict[str, Any]) -> dict[str, Any]:
    """
    Shape a stored alarm the way the second step's form expects it.

    Returns:
        The sound settings of the alarm, without the derived Music Assistant toggle.

    """
    return {key: data[key] for key in SOUND_KEYS if key in data and key != CONF_AUDIO_USE_MUSIC_ASSISTANT}


def _advanced_schema(hass: HomeAssistant) -> vol.Schema:
    """
    Return the fields that have a usable default.

    Returns:
        The schema for the collapsed section.

    """
    schema = vol.Schema(
        {
            vol.Required(CONF_RAMP_MINUTES, default=DEFAULT_RAMP_MINUTES): _minutes_selector(MAX_RAMP_MINUTES),
            vol.Required(CONF_SNOOZE_MINUTES, default=DEFAULT_SNOOZE_MINUTES): _minutes_selector(MAX_SNOOZE_MINUTES),
            vol.Optional(CONF_GATE_ENTITY): selector.EntitySelector(),
            vol.Optional(CONF_GATE_STATE, default=DEFAULT_GATE_STATE): selector.TextSelector(),
        },
    )

    targets = _notify_options(hass)
    if targets:
        schema = schema.extend(
            {
                vol.Optional(CONF_NOTIFY_TARGETS, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=targets,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    ),
                ),
                vol.Required(CONF_PHONE_CRITICAL_SOUND, default=True): selector.BooleanSelector(),
            },
        )

    return schema


async def _async_music_assistant_playlists(hass: HomeAssistant) -> list[selector.SelectOptionDict]:
    """
    Return the playlists of every loaded Music Assistant instance.

    Returns:
        One option per playlist, valued by its Music Assistant URI — empty when Music
        Assistant is absent, still starting up, or cannot be reached.

    """
    if not hass.services.has_service(MUSIC_ASSISTANT_DOMAIN, MUSIC_ASSISTANT_SERVICE_GET_LIBRARY):
        return []

    options: list[selector.SelectOptionDict] = []
    for entry in hass.config_entries.async_entries(MUSIC_ASSISTANT_DOMAIN):
        if entry.state is not ConfigEntryState.LOADED:
            continue

        try:
            async with asyncio.timeout(PLAYLIST_FETCH_TIMEOUT_SECONDS):
                response = await hass.services.async_call(
                    MUSIC_ASSISTANT_DOMAIN,
                    MUSIC_ASSISTANT_SERVICE_GET_LIBRARY,
                    {
                        ATTR_MA_CONFIG_ENTRY_ID: entry.entry_id,
                        ATTR_MA_MEDIA_TYPE: MUSIC_ASSISTANT_MEDIA_TYPE_PLAYLIST,
                        ATTR_MA_LIMIT: PLAYLIST_FETCH_LIMIT,
                    },
                    blocking=True,
                    return_response=True,
                )
        except (HomeAssistantError, TimeoutError) as exception:
            LOGGER.warning("Could not list the Music Assistant playlists for the alarm form: %s", exception)
            continue

        items = (response or {}).get(ATTR_MA_ITEMS)
        if not isinstance(items, list):
            continue

        options.extend(
            selector.SelectOptionDict(value=str(item[ATTR_MA_URI]), label=str(item[ATTR_MA_NAME]))
            for item in items
            if isinstance(item, dict) and item.get(ATTR_MA_URI)
        )

    return options


def _minutes_selector(maximum: int, *, minimum: int = 1) -> selector.NumberSelector:
    """
    Return a whole-minute number field.

    Returns:
        The selector for a duration in minutes.

    """
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=1,
            unit_of_measurement="min",
            mode=selector.NumberSelectorMode.BOX,
        ),
    )


def _percentage_selector() -> selector.NumberSelector:
    """
    Return a whole-percent volume field.

    Returns:
        The selector for a volume percentage.

    """
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=100,
            step=1,
            unit_of_measurement=PERCENTAGE,
            mode=selector.NumberSelectorMode.BOX,
        ),
    )


def _notify_options(hass: HomeAssistant) -> list[selector.SelectOptionDict]:
    """
    Return the companion app notify services this installation offers.

    Returns:
        One option per `notify.mobile_app_*` service, sorted by label.

    """
    services = hass.services.async_services().get(NOTIFY_DOMAIN, {})

    return sorted(
        (
            selector.SelectOptionDict(
                value=service,
                label=service.removeprefix(NOTIFY_SERVICE_PREFIX).replace("_", " ").title(),
            )
            for service in services
            if service.startswith(NOTIFY_SERVICE_PREFIX)
        ),
        key=lambda option: option["label"],
    )
