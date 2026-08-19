"""Subentry flow for ha_alarm_clock — one subentry per alarm."""

from typing import Any

from custom_components.ha_alarm_clock.const import AUDIO_MODE_NONE, CONF_AUDIO_MODE
from homeassistant.config_entries import ConfigSubentryFlow, SubentryFlowResult
from homeassistant.const import CONF_NAME

from .schemas import async_get_alarm_schema, async_get_sound_schema, merge_alarm, to_form_data, to_sound_form_data
from .validators import async_validate_alarm_audio


class AlarmSubentryFlowHandler(ConfigSubentryFlow):
    """Add and edit the alarms of the Sunrise Alarm entry."""

    def __init__(self) -> None:
        """Initialize the flow."""
        self._main: dict[str, Any] = {}
        self._reconfiguring = False

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        """
        Add an alarm.

        Returns:
            The form, the sound step, or the created subentry.

        """
        if user_input is not None:
            self._main = user_input

            if user_input.get(CONF_AUDIO_MODE, AUDIO_MODE_NONE) != AUDIO_MODE_NONE:
                return await self.async_step_sound()

            alarm = merge_alarm(user_input, None)
            return self.async_create_entry(title=alarm[CONF_NAME], data=alarm)

        return self.async_show_form(step_id="user", data_schema=async_get_alarm_schema(self.hass))

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        """
        Edit an existing alarm.

        Returns:
            The form, the sound step, or the abort that follows the update.

        """
        subentry = self._get_reconfigure_subentry()
        self._reconfiguring = True

        if user_input is not None:
            self._main = user_input

            if user_input.get(CONF_AUDIO_MODE, AUDIO_MODE_NONE) != AUDIO_MODE_NONE:
                return await self.async_step_sound()

            alarm = merge_alarm(user_input, None)
            return self.async_update_and_abort(self._get_entry(), subentry, title=alarm[CONF_NAME], data=alarm)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                async_get_alarm_schema(self.hass),
                to_form_data(dict(subentry.data)),
            ),
        )

    async def async_step_sound(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        """
        Collect the sound settings for the chosen mode.

        Returns:
            The form, the created subentry, or the abort that follows the update.

        """
        mode = self._main.get(CONF_AUDIO_MODE, AUDIO_MODE_NONE)
        errors: dict[str, str] = {}

        if user_input is not None:
            alarm = merge_alarm(self._main, user_input)
            errors = async_validate_alarm_audio(self.hass, alarm)

            if not errors:
                if self._reconfiguring:
                    return self.async_update_and_abort(
                        self._get_entry(),
                        self._get_reconfigure_subentry(),
                        title=alarm[CONF_NAME],
                        data=alarm,
                    )

                return self.async_create_entry(title=alarm[CONF_NAME], data=alarm)

        suggested = user_input
        if suggested is None and self._reconfiguring:
            suggested = to_sound_form_data(dict(self._get_reconfigure_subentry().data))

        schema = await async_get_sound_schema(self.hass, mode)
        if suggested:
            schema = self.add_suggested_values_to_schema(schema, suggested)

        return self.async_show_form(step_id="sound", data_schema=schema, errors=errors)


__all__ = ["AlarmSubentryFlowHandler"]
