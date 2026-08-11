"""Buttons for snoozing and dismissing a ringing alarm."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from custom_components.ha_alarm_clock.entity import SunriseAlarmEntity
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription

if TYPE_CHECKING:
    from custom_components.ha_alarm_clock.utils.scheduler import AlarmScheduler


@dataclass(frozen=True, kw_only=True)
class SunriseAlarmButtonEntityDescription(ButtonEntityDescription):
    """Describes a button and what pressing it does to the alarm."""

    press_fn: Callable[[AlarmScheduler, str], Coroutine[Any, Any, None]]


ENTITY_DESCRIPTIONS: tuple[SunriseAlarmButtonEntityDescription, ...] = (
    SunriseAlarmButtonEntityDescription(
        key="snooze",
        translation_key="snooze",
        press_fn=lambda scheduler, subentry_id: scheduler.async_snooze(subentry_id),
    ),
    SunriseAlarmButtonEntityDescription(
        key="dismiss",
        translation_key="dismiss",
        press_fn=lambda scheduler, subentry_id: scheduler.async_dismiss(subentry_id),
    ),
)


class SunriseAlarmButton(ButtonEntity, SunriseAlarmEntity):
    """Button acting on the alarm's current wake-up cycle."""

    entity_description: SunriseAlarmButtonEntityDescription

    async def async_press(self) -> None:
        """Snooze or dismiss the alarm."""
        scheduler = self.coordinator.config_entry.runtime_data.scheduler
        await self.entity_description.press_fn(scheduler, self._subentry_id)
