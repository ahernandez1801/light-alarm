"""Switches for arming an alarm and making it fire only once."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from custom_components.ha_alarm_clock.coordinator import SunriseAlarmDataUpdateCoordinator
from custom_components.ha_alarm_clock.data import AlarmState
from custom_components.ha_alarm_clock.entity import SunriseAlarmEntity
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory


@dataclass(frozen=True, kw_only=True)
class SunriseAlarmSwitchEntityDescription(SwitchEntityDescription):
    """Describes a switch, how to read it and how to write it."""

    value_fn: Callable[[AlarmState], bool]
    set_fn: Callable[
        [SunriseAlarmDataUpdateCoordinator, str, bool],
        Coroutine[Any, Any, None],
    ]


ENTITY_DESCRIPTIONS: tuple[SunriseAlarmSwitchEntityDescription, ...] = (
    SunriseAlarmSwitchEntityDescription(
        key="alarm_enabled",
        translation_key="alarm_enabled",
        value_fn=lambda alarm: alarm.enabled,
        set_fn=lambda coordinator, subentry_id, on: coordinator.async_set_enabled(subentry_id, enabled=on),
    ),
    SunriseAlarmSwitchEntityDescription(
        key="one_time",
        translation_key="one_time",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda alarm: alarm.one_time,
        set_fn=lambda coordinator, subentry_id, on: coordinator.async_set_one_time(subentry_id, one_time=on),
    ),
)


class SunriseAlarmSwitch(SwitchEntity, SunriseAlarmEntity):
    """Switch for one of an alarm's boolean settings."""

    entity_description: SunriseAlarmSwitchEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return the value read from coordinator data."""
        alarm = self.alarm
        return None if alarm is None else self.entity_description.value_fn(alarm)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the setting on."""
        await self.entity_description.set_fn(self.coordinator, self._subentry_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the setting off."""
        await self.entity_description.set_fn(self.coordinator, self._subentry_id, False)
