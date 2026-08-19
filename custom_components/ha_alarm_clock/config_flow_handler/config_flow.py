"""Config flow for ha_alarm_clock — creates the entry and its first alarm."""

from typing import Any

from custom_components.ha_alarm_clock.const import (
    AUDIO_MODE_NONE,
    CONF_AUDIO_MODE,
    DEFAULT_ENTRY_TITLE,
    DOMAIN,
    SUBENTRY_TYPE_ALARM,
)
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback

from .schemas import async_get_alarm_schema, async_get_sound_schema, merge_alarm
from .subentry_flow import AlarmSubentryFlowHandler
from .validators import async_validate_alarm_audio


class SunriseAlarmConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for ha_alarm_clock."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._main: dict[str, Any] = {}

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls,
        config_entry: config_entries.ConfigEntry,
    ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
        """
        Declare the subentry types this entry supports.

        Returns:
            The alarm subentry flow, keyed by its type.

        """
        return {SUBENTRY_TYPE_ALARM: AlarmSubentryFlowHandler}

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle a flow started by the user, collecting the first alarm.

        Returns:
            The form, the sound step, or the created config entry.

        """
        if user_input is not None:
            self._main = user_input

            if user_input.get(CONF_AUDIO_MODE, AUDIO_MODE_NONE) != AUDIO_MODE_NONE:
                return await self.async_step_sound()

            return self._async_create_alarm_entry(merge_alarm(user_input, None))

        return self.async_show_form(step_id="user", data_schema=async_get_alarm_schema(self.hass))

    async def async_step_sound(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Collect the sound settings for the chosen mode.

        Returns:
            The form, or the created config entry.

        """
        mode = self._main.get(CONF_AUDIO_MODE, AUDIO_MODE_NONE)
        errors: dict[str, str] = {}

        if user_input is not None:
            alarm = merge_alarm(self._main, user_input)
            errors = async_validate_alarm_audio(self.hass, alarm)

            if not errors:
                return self._async_create_alarm_entry(alarm)

        schema = await async_get_sound_schema(self.hass, mode)
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)

        return self.async_show_form(step_id="sound", data_schema=schema, errors=errors)

    @callback
    def _async_create_alarm_entry(self, alarm: dict[str, Any]) -> config_entries.ConfigFlowResult:
        """
        Create the config entry with the collected alarm as its first subentry.

        Returns:
            The created config entry.

        """
        return self.async_create_entry(
            title=DEFAULT_ENTRY_TITLE,
            data={},
            subentries=[
                config_entries.ConfigSubentryData(
                    data=alarm,
                    subentry_type=SUBENTRY_TYPE_ALARM,
                    title=alarm[CONF_NAME],
                    unique_id=None,
                ),
            ],
        )


__all__ = ["SunriseAlarmConfigFlowHandler"]
