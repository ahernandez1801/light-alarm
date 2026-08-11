"""Editable alarm time, so an alarm can be changed from a dashboard."""

from datetime import time

from custom_components.ha_alarm_clock.const import CONF_ALARM_TIME
from custom_components.ha_alarm_clock.entity import SunriseAlarmEntity
from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.util import dt as dt_util

ENTITY_DESCRIPTIONS: tuple[TimeEntityDescription, ...] = (
    TimeEntityDescription(
        key="alarm_time",
        translation_key="alarm_time",
    ),
)


class SunriseAlarmTime(TimeEntity, SunriseAlarmEntity):
    """The time this alarm starts its sunrise."""

    @property
    def native_value(self) -> time | None:
        """Return the configured alarm time."""
        subentry = self.coordinator.config_entry.subentries.get(self._subentry_id)
        if subentry is None:
            return None

        return dt_util.parse_time(str(subentry.data.get(CONF_ALARM_TIME, "")))

    async def async_set_value(self, value: time) -> None:
        """Move the alarm to a new time and re-arm it."""
        self.coordinator.async_update_alarm_config(
            self._subentry_id,
            {CONF_ALARM_TIME: value.isoformat()},
        )
