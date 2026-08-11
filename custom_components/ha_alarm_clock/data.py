"""
Runtime data types for ha_alarm_clock.

Access pattern: entry.runtime_data.coordinator / entry.runtime_data.scheduler
"""

from dataclasses import dataclass, replace
from datetime import datetime
from typing import TYPE_CHECKING

from custom_components.ha_alarm_clock.const import AlarmPhase

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .coordinator import SunriseAlarmDataUpdateCoordinator
    from .utils.audio import AlarmAudio
    from .utils.notifier import AlarmNotifier
    from .utils.scheduler import AlarmScheduler


type SunriseAlarmConfigEntry = ConfigEntry[SunriseAlarmData]


@dataclass(frozen=True)
class AlarmState:
    """
    The live state of one alarm, keyed in coordinator data by its subentry ID.

    `enabled` and `one_time` are user-writable and persisted; `phase` and `next_fire`
    are derived by the scheduler and rebuilt from scratch after a restart.
    """

    enabled: bool
    one_time: bool
    phase: AlarmPhase = AlarmPhase.IDLE
    next_fire: datetime | None = None

    def with_phase(self, phase: AlarmPhase, next_fire: datetime | None) -> AlarmState:
        """
        Return a copy in a new phase.

        Returns:
            The updated state.

        """
        return replace(self, phase=phase, next_fire=next_fire)


@dataclass
class SunriseAlarmData:
    """Runtime data stored on the config entry after a successful setup."""

    coordinator: SunriseAlarmDataUpdateCoordinator
    notifier: AlarmNotifier
    audio: AlarmAudio
    scheduler: AlarmScheduler
    subentry_ids: set[str]
    integration: Integration
