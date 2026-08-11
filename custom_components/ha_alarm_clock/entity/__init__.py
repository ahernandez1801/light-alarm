"""
Entity package for ha_alarm_clock.

Architecture:
    All platform entities inherit from (PlatformEntity, SunriseAlarmEntity).
    MRO order matters — platform-specific class first, then the integration base.
    Entities read data from coordinator.data and NEVER call the API client directly.
    Unique IDs follow the pattern: {entry_id}_{description.key}

See entity/base.py for the SunriseAlarmEntity base class.
"""

from .base import SunriseAlarmEntity

__all__ = ["SunriseAlarmEntity"]
