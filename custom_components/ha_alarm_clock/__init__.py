"""
Custom integration to integrate ha_alarm_clock with Home Assistant.

For more details about this integration, please refer to:
https://github.com/ahernandez1801/light-alarm
"""

from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.helpers.config_validation as cv
from homeassistant.loader import async_get_loaded_integration

from .const import DOMAIN
from .coordinator import SunriseAlarmDataUpdateCoordinator
from .data import SunriseAlarmData
from .service_actions import async_setup_services
from .utils.audio import AlarmAudio
from .utils.notifier import AlarmNotifier, async_setup_action_listener
from .utils.scheduler import AlarmScheduler

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import SunriseAlarmConfigEntry

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """
    Register the service actions.

    Returns:
        True once the actions are registered.

    """
    await async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SunriseAlarmConfigEntry,
) -> bool:
    """
    Set up a config entry.

    Returns:
        True once every alarm is armed and every platform is forwarded.

    """
    coordinator = SunriseAlarmDataUpdateCoordinator(hass, entry)
    await coordinator.async_load()

    notifier = AlarmNotifier(hass, coordinator)
    audio = AlarmAudio(hass, coordinator)
    scheduler = AlarmScheduler(hass, coordinator, notifier, audio)
    coordinator.scheduler = scheduler

    entry.runtime_data = SunriseAlarmData(
        coordinator=coordinator,
        notifier=notifier,
        audio=audio,
        scheduler=scheduler,
        subentry_ids=set(entry.subentries),
        integration=async_get_loaded_integration(hass, entry.domain),
    )

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _async_remove_stale_registry_entries(hass, entry)

    scheduler.async_start()
    entry.async_on_unload(scheduler.async_stop)
    entry.async_on_unload(async_setup_action_listener(hass, scheduler))
    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: SunriseAlarmConfigEntry,
) -> bool:
    """
    Unload a config entry.

    Returns:
        True if every platform unloaded cleanly.

    """
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_listener(
    hass: HomeAssistant,
    entry: SunriseAlarmConfigEntry,
) -> None:
    """
    React to a changed entry without reloading more than necessary.

    Adding or removing an alarm changes which entities have to exist, so that needs a
    reload. Editing one — from its dialog, or from its `time` and `number` entities —
    only needs the alarm re-armed, and reloading there would cancel a wake-up in
    progress and make every dashboard edit flicker.
    """
    data = entry.runtime_data

    if set(entry.subentries) != data.subentry_ids:
        await hass.config_entries.async_reload(entry.entry_id)
        return

    for subentry_id in entry.subentries:
        data.scheduler.async_reconfigure(subentry_id)


def _async_remove_stale_registry_entries(
    hass: HomeAssistant,
    entry: SunriseAlarmConfigEntry,
) -> None:
    """
    Drop registry entries that no live alarm backs.

    Every entity sits on the entry's single shared device rather than on a device per
    subentry, so deleting an alarm no longer cascades through the registry — its
    entities, and any per-alarm device left over from an older version, are removed
    here on the reload that follows.
    """
    live_prefixes = tuple(f"{subentry_id}_" for subentry_id in entry.subentries)

    entity_registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if not entity_entry.unique_id.startswith(live_prefixes):
            entity_registry.async_remove(entity_entry.entity_id)

    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if (DOMAIN, entry.entry_id) not in device.identifiers:
            device_registry.async_remove_device(device.id)
