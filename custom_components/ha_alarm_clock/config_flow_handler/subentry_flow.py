"""Subentry flow for ha_alarm_clock — one subentry per alarm."""

from typing import Any

from homeassistant.config_entries import ConfigSubentryFlow, SubentryFlowResult
from homeassistant.const import CONF_NAME

from .schemas import async_get_alarm_schema, flatten_alarm_input, to_form_data
from .validators import async_validate_alarm_audio


class AlarmSubentryFlowHandler(ConfigSubentryFlow):
    """Add and edit the alarms of the Sunrise Alarm entry."""

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        """
        Add an alarm.

        Returns:
            The form, or the created subentry.

        """
        errors: dict[str, str] = {}

        if user_input is not None:
            alarm = flatten_alarm_input(user_input)
            errors = async_validate_alarm_audio(self.hass, alarm)

            if not errors:
                return self.async_create_entry(title=alarm[CONF_NAME], data=alarm)

        schema = await async_get_alarm_schema(self.hass)
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        """
        Edit an existing alarm.

        Returns:
            The form, or the abort that follows the update.

        """
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}

        if user_input is not None:
            alarm = flatten_alarm_input(user_input)
            errors = async_validate_alarm_audio(self.hass, alarm)

            if not errors:
                return self.async_update_and_abort(
                    self._get_entry(),
                    subentry,
                    title=alarm[CONF_NAME],
                    data=alarm,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                await async_get_alarm_schema(self.hass),
                user_input if user_input is not None else to_form_data(dict(subentry.data)),
            ),
            errors=errors,
        )


__all__ = ["AlarmSubentryFlowHandler"]
