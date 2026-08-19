"""Subentry flow for ha_alarm_clock — one subentry per alarm."""

from typing import Any

from homeassistant.config_entries import ConfigSubentryFlow, SubentryFlowResult
from homeassistant.const import CONF_NAME

from .schemas import async_get_alarm_schema, flatten_alarm_input, to_form_data


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
        if user_input is not None:
            alarm = flatten_alarm_input(user_input)
            return self.async_create_entry(title=alarm[CONF_NAME], data=alarm)

        return self.async_show_form(step_id="user", data_schema=await async_get_alarm_schema(self.hass))

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

        if user_input is not None:
            alarm = flatten_alarm_input(user_input)
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
                to_form_data(dict(subentry.data)),
            ),
        )


__all__ = ["AlarmSubentryFlowHandler"]
