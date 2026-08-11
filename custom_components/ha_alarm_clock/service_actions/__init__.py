"""Service action registration for ha_alarm_clock."""

from typing import TYPE_CHECKING

import voluptuous as vol

from custom_components.ha_alarm_clock.const import DOMAIN
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.helpers import config_validation as cv

from .alarm_control import async_handle_dismiss, async_handle_snooze

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

SERVICE_SNOOZE = "snooze"
SERVICE_DISMISS = "dismiss"

TARGET_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
    },
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's service actions once, at component level."""

    async def handle_snooze(call: ServiceCall) -> None:
        """Run the snooze action."""
        await async_handle_snooze(hass, call)

    async def handle_dismiss(call: ServiceCall) -> None:
        """Run the dismiss action."""
        await async_handle_dismiss(hass, call)

    if not hass.services.has_service(DOMAIN, SERVICE_SNOOZE):
        hass.services.async_register(DOMAIN, SERVICE_SNOOZE, handle_snooze, schema=TARGET_SCHEMA)

    if not hass.services.has_service(DOMAIN, SERVICE_DISMISS):
        hass.services.async_register(DOMAIN, SERVICE_DISMISS, handle_dismiss, schema=TARGET_SCHEMA)
