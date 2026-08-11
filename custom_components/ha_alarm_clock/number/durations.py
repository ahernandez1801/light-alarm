"""Editable sunrise and snooze lengths."""

from dataclasses import dataclass

from custom_components.ha_alarm_clock.const import (
    CONF_RAMP_MINUTES,
    CONF_SNOOZE_MINUTES,
    DEFAULT_RAMP_MINUTES,
    DEFAULT_SNOOZE_MINUTES,
    MAX_RAMP_MINUTES,
    MAX_SNOOZE_MINUTES,
)
from custom_components.ha_alarm_clock.entity import SunriseAlarmEntity
from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime


@dataclass(frozen=True, kw_only=True)
class SunriseAlarmNumberEntityDescription(NumberEntityDescription):
    """Describes a number and which alarm setting it edits."""

    config_key: str
    default: int


ENTITY_DESCRIPTIONS: tuple[SunriseAlarmNumberEntityDescription, ...] = (
    SunriseAlarmNumberEntityDescription(
        key="ramp_minutes",
        translation_key="ramp_minutes",
        config_key=CONF_RAMP_MINUTES,
        default=DEFAULT_RAMP_MINUTES,
        entity_category=EntityCategory.CONFIG,
        native_min_value=1,
        native_max_value=MAX_RAMP_MINUTES,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.BOX,
    ),
    SunriseAlarmNumberEntityDescription(
        key="snooze_minutes",
        translation_key="snooze_minutes",
        config_key=CONF_SNOOZE_MINUTES,
        default=DEFAULT_SNOOZE_MINUTES,
        entity_category=EntityCategory.CONFIG,
        native_min_value=1,
        native_max_value=MAX_SNOOZE_MINUTES,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.BOX,
    ),
)


class SunriseAlarmNumber(NumberEntity, SunriseAlarmEntity):
    """One of the alarm's durations, in minutes."""

    entity_description: SunriseAlarmNumberEntityDescription

    @property
    def native_value(self) -> float | None:
        """Return the configured duration."""
        subentry = self.coordinator.config_entry.subentries.get(self._subentry_id)
        if subentry is None:
            return None

        return float(subentry.data.get(self.entity_description.config_key, self.entity_description.default))

    async def async_set_native_value(self, value: float) -> None:
        """Store the new duration on the alarm."""
        self.coordinator.async_update_alarm_config(
            self._subentry_id,
            {self.entity_description.config_key: int(value)},
        )
