"""Sensor reporting when an alarm next fires."""

from datetime import datetime

from custom_components.ha_alarm_clock.entity import SunriseAlarmEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription

ENTITY_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="next_alarm",
        translation_key="next_alarm",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)


class SunriseAlarmNextAlarmSensor(SensorEntity, SunriseAlarmEntity):
    """
    When this alarm next acts.

    While an alarm is snoozed this is the end of the snooze, and while it is ramping it
    is when the ramp finishes — in both cases the next thing the alarm will do.
    """

    @property
    def native_value(self) -> datetime | None:
        """Return the next fire time, or None when the alarm is disarmed."""
        alarm = self.alarm
        return None if alarm is None else alarm.next_fire
