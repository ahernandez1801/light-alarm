"""Config flow for ha_alarm_clock — creates the entry and its first alarm."""

from typing import Any

from custom_components.ha_alarm_clock.const import DEFAULT_ENTRY_TITLE, DOMAIN, SUBENTRY_TYPE_ALARM
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback

from .schemas import flatten_alarm_input, get_alarm_schema
from .subentry_flow import AlarmSubentryFlowHandler


class SunriseAlarmConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for ha_alarm_clock."""

    VERSION = 1

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
            The form, or the created config entry.

        """
        if user_input is not None:
            alarm = flatten_alarm_input(user_input)
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

        return self.async_show_form(step_id="user", data_schema=get_alarm_schema(self.hass))


__all__ = ["SunriseAlarmConfigFlowHandler"]
