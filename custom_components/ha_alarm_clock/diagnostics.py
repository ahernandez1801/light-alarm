"""
Diagnostics support for ha_alarm_clock.

https://developers.home-assistant.io/docs/core/integration_diagnostics
"""

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.redact import async_redact_data

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import AlarmState, SunriseAlarmConfigEntry

TO_REDACT = {
    "api_key",
    "latitude",
    "longitude",
    "token",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: SunriseAlarmConfigEntry,
) -> dict[str, Any]:
    """
    Return diagnostics for a config entry.

    Returns:
        The redacted entry configuration and the current state of every alarm.

    """
    coordinator = entry.runtime_data.coordinator

    return {
        "entry": {
            "version": entry.version,
            "minor_version": entry.minor_version,
            "state": str(entry.state),
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
        },
        "alarms": {
            subentry_id: {
                "config": async_redact_data(dict(subentry.data), TO_REDACT),
                "state": _state_dict(coordinator.data.get(subentry_id)),
            }
            for subentry_id, subentry in entry.subentries.items()
        },
    }


def _state_dict(state: AlarmState | None) -> dict[str, Any] | None:
    """
    Render one alarm state as JSON-serializable values.

    Returns:
        The alarm's state, or None when it has none yet.

    """
    if state is None:
        return None

    return {
        "enabled": state.enabled,
        "one_time": state.one_time,
        "phase": str(state.phase),
        "next_fire": state.next_fire.isoformat() if state.next_fire else None,
    }
