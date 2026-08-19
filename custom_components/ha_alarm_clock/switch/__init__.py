"""Switch platform for ha_alarm_clock."""

from typing import TYPE_CHECKING

from .alarm_switch import ENTITY_DESCRIPTIONS, SunriseAlarmSwitch

# Acts on the alarm: the coordinator does not limit outbound calls.
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
    """Set up the switch platform, one set of switches per alarm."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        SunriseAlarmSwitch(coordinator, subentry, description)
        for subentry in entry.subentries.values()
        for description in ENTITY_DESCRIPTIONS
    )
