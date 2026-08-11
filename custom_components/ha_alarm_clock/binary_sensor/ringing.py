"""Binary sensor reporting whether an alarm is currently ringing."""

from custom_components.ha_alarm_clock.const import AlarmPhase
from custom_components.ha_alarm_clock.entity import SunriseAlarmEntity
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription

ENTITY_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="ringing",
        translation_key="ringing",
    ),
)


class SunriseAlarmRingingBinarySensor(BinarySensorEntity, SunriseAlarmEntity):
    """On once the sunrise ramp has finished and the alarm is waiting to be dismissed."""

    @property
    def is_on(self) -> bool | None:
        """Return whether this alarm is ringing."""
        alarm = self.alarm
        return None if alarm is None else alarm.phase is AlarmPhase.RINGING
