"""Handlers for the snooze and dismiss actions."""

from typing import TYPE_CHECKING

from custom_components.ha_alarm_clock.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

if TYPE_CHECKING:
    from custom_components.ha_alarm_clock.data import SunriseAlarmConfigEntry
    from custom_components.ha_alarm_clock.utils.scheduler import AlarmScheduler
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.helpers.device_registry import DeviceEntry


async def async_handle_snooze(hass: HomeAssistant, call: ServiceCall) -> None:
    """Snooze every alarm the call targets."""
    for scheduler, subentry_id in _async_resolve(hass, call):
        await scheduler.async_snooze(subentry_id)


async def async_handle_dismiss(hass: HomeAssistant, call: ServiceCall) -> None:
    """Dismiss every alarm the call targets."""
    for scheduler, subentry_id in _async_resolve(hass, call):
        await scheduler.async_dismiss(subentry_id)


def _async_resolve(hass: HomeAssistant, call: ServiceCall) -> list[tuple[AlarmScheduler, str]]:
    """
    Turn the targeted devices into the alarms behind them.

    Returns:
        One scheduler and subentry ID per targeted alarm.

    Raises:
        ServiceValidationError: If a targeted device is not an alarm of a loaded entry.

    """
    registry = dr.async_get(hass)
    resolved: list[tuple[AlarmScheduler, str]] = []

    for device_id in call.data[ATTR_DEVICE_ID]:
        device = registry.async_get(device_id)
        subentry_id = (
            next(
                (identifier for domain, identifier in device.identifiers if domain == DOMAIN),
                None,
            )
            if device is not None
            else None
        )
        entry = _async_loaded_entry(hass, device) if device is not None else None

        if subentry_id is None or entry is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="alarm_not_found",
                translation_placeholders={"target": device_id},
            )

        resolved.append((entry.runtime_data.scheduler, subentry_id))

    return resolved


def _async_loaded_entry(hass: HomeAssistant, device: DeviceEntry) -> SunriseAlarmConfigEntry | None:
    """
    Return this integration's loaded config entry for a device.

    Returns:
        The entry, or None when it is missing or not loaded.

    """
    for entry_id in device.config_entries:
        entry: ConfigEntry | None = hass.config_entries.async_get_entry(entry_id)
        if entry is not None and entry.domain == DOMAIN and entry.state is ConfigEntryState.LOADED:
            return entry

    return None
