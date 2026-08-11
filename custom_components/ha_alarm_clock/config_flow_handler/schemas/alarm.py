"""Voluptuous schema for the alarm dialog, shared by setup, add and reconfigure."""

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from custom_components.ha_alarm_clock.const import (
    CONF_ALARM_TIME,
    CONF_AUDIO_MEDIA,
    CONF_AUDIO_RADIO_MODE,
    CONF_AUDIO_TARGETS,
    CONF_AUDIO_USE_MUSIC_ASSISTANT,
    CONF_AUDIO_VOLUME_END,
    CONF_AUDIO_VOLUME_MINUTES,
    CONF_AUDIO_VOLUME_START,
    CONF_LIGHTS,
    CONF_NOTIFY_TARGETS,
    CONF_PHONE_CRITICAL_SOUND,
    CONF_RAMP_MINUTES,
    CONF_SNOOZE_MINUTES,
    DEFAULT_AUDIO_VOLUME_END,
    DEFAULT_AUDIO_VOLUME_MINUTES,
    DEFAULT_AUDIO_VOLUME_START,
    DEFAULT_RAMP_MINUTES,
    DEFAULT_SNOOZE_MINUTES,
    MAX_AUDIO_VOLUME_MINUTES,
    MAX_RAMP_MINUTES,
    MAX_SNOOZE_MINUTES,
    MUSIC_ASSISTANT_DOMAIN,
    MUSIC_ASSISTANT_SERVICE_PLAY_MEDIA,
    NOTIFY_DOMAIN,
    NOTIFY_SERVICE_PREFIX,
    SECTION_ADVANCED,
    SECTION_SOUND,
)
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import CONF_NAME, PERCENTAGE
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

DEFAULT_ALARM_TIME = "07:00:00"

ADVANCED_KEYS = (CONF_RAMP_MINUTES, CONF_SNOOZE_MINUTES, CONF_NOTIFY_TARGETS)
SOUND_KEYS = (
    CONF_AUDIO_TARGETS,
    CONF_AUDIO_MEDIA,
    CONF_AUDIO_USE_MUSIC_ASSISTANT,
    CONF_AUDIO_RADIO_MODE,
    CONF_AUDIO_VOLUME_START,
    CONF_AUDIO_VOLUME_END,
    CONF_AUDIO_VOLUME_MINUTES,
    CONF_PHONE_CRITICAL_SOUND,
)
SECTIONS = (SECTION_ADVANCED, SECTION_SOUND)


def get_alarm_schema(hass: HomeAssistant) -> vol.Schema:
    """
    Return the schema describing one alarm.

    Name, time and lights are the whole dialog; everything that has a sensible default
    sits in a collapsed section, so adding an alarm is three fields.

    Returns:
        The schema for the alarm form.

    """
    return vol.Schema(
        {
            vol.Required(CONF_NAME): selector.TextSelector(),
            vol.Required(CONF_ALARM_TIME, default=DEFAULT_ALARM_TIME): selector.TimeSelector(),
            vol.Required(CONF_LIGHTS): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=LIGHT_DOMAIN, multiple=True),
            ),
            vol.Required(SECTION_SOUND): section(_sound_schema(hass), {"collapsed": True}),
            vol.Required(SECTION_ADVANCED): section(_advanced_schema(hass), {"collapsed": True}),
        },
    )


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


def to_form_data(data: dict[str, Any]) -> dict[str, Any]:
    """
    Shape a stored alarm the way the form expects it.

    Returns:
        The alarm configuration with its section keys nested in their sections.

    """
    nested_keys = ADVANCED_KEYS + SOUND_KEYS
    return {
        **{key: value for key, value in data.items() if key not in nested_keys},
        SECTION_SOUND: {key: data[key] for key in SOUND_KEYS if key in data},
        SECTION_ADVANCED: {key: data[key] for key in ADVANCED_KEYS if key in data},
    }


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
            },
        )

    return schema


def _sound_schema(hass: HomeAssistant) -> vol.Schema:
    """
    Return the audio fields, offering only what the installation has.

    The Music Assistant toggles appear only when that integration is installed, and the
    phone sound toggle only when a companion app is around to carry it.

    Returns:
        The schema for the collapsed sound section.

    """
    schema = vol.Schema(
        {
            vol.Optional(CONF_AUDIO_TARGETS, default=[]): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=MEDIA_PLAYER_DOMAIN, multiple=True),
            ),
            vol.Optional(CONF_AUDIO_MEDIA): selector.MediaSelector(),
            vol.Required(CONF_AUDIO_VOLUME_START, default=DEFAULT_AUDIO_VOLUME_START): _percentage_selector(),
            vol.Required(CONF_AUDIO_VOLUME_END, default=DEFAULT_AUDIO_VOLUME_END): _percentage_selector(),
            vol.Required(CONF_AUDIO_VOLUME_MINUTES, default=DEFAULT_AUDIO_VOLUME_MINUTES): _minutes_selector(
                MAX_AUDIO_VOLUME_MINUTES,
                minimum=0,
            ),
        },
    )

    if hass.services.has_service(MUSIC_ASSISTANT_DOMAIN, MUSIC_ASSISTANT_SERVICE_PLAY_MEDIA):
        schema = schema.extend(
            {
                vol.Required(CONF_AUDIO_USE_MUSIC_ASSISTANT, default=False): selector.BooleanSelector(),
                vol.Required(CONF_AUDIO_RADIO_MODE, default=False): selector.BooleanSelector(),
            },
        )

    if _notify_options(hass):
        schema = schema.extend(
            {
                vol.Required(CONF_PHONE_CRITICAL_SOUND, default=True): selector.BooleanSelector(),
            },
        )

    return schema


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
