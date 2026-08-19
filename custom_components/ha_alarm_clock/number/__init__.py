"""Number platform for ha_alarm_clock."""

from typing import TYPE_CHECKING

from .durations import ENTITY_DESCRIPTIONS, SunriseAlarmNumber

# Writes the alarm's configuration back to its subentry.
PARALLEL_UPDATES = 1

if TYPE_CHECKING:
    from custom_components.ha_alarm_clock.data import SunriseAlarmConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SunriseAlarmConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number platform, one pair per alarm."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        SunriseAlarmNumber(coordinator, subentry, description)
        for subentry in entry.subentries.values()
        for description in ENTITY_DESCRIPTIONS
    )
