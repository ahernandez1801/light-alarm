"""Sensor platform for ha_alarm_clock."""

from typing import TYPE_CHECKING

from .next_alarm import ENTITY_DESCRIPTIONS, SunriseAlarmNextAlarmSensor

# Read-only platform: the coordinator already serializes the state.
PARALLEL_UPDATES = 0

if TYPE_CHECKING:
    from custom_components.ha_alarm_clock.data import SunriseAlarmConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SunriseAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform, one per alarm."""
    coordinator = entry.runtime_data.coordinator

    for subentry_id, subentry in entry.subentries.items():
        async_add_entities(
            (SunriseAlarmNextAlarmSensor(coordinator, subentry, description) for description in ENTITY_DESCRIPTIONS),
            config_subentry_id=subentry_id,
        )
