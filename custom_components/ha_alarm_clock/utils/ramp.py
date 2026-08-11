"""Light control for the sunrise ramp."""

from typing import TYPE_CHECKING

from custom_components.ha_alarm_clock.const import DOMAIN
from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_TRANSITION, DOMAIN as LIGHT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.exceptions import HomeAssistantError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from homeassistant.core import HomeAssistant

BRIGHTNESS_START = 1
BRIGHTNESS_FULL = 255


async def async_start_ramp(
    hass: HomeAssistant,
    lights: Sequence[str],
    ramp_seconds: int,
    *,
    reset: bool = True,
) -> None:
    """
    Take the lights to their dimmest, then transition them to full over the ramp.

    The caller passes the time remaining until the alarm rings rather than the alarm's
    configured sunrise length, so a sunrise that started late still arrives at full
    brightness exactly on time.

    `reset` is false when picking a ramp back up after a restart: the lights are already
    part-way up, and dropping them to their dimmest first would undo that.

    Raises:
        HomeAssistantError: If a light rejected the call.

    """
    if not lights:
        return

    try:
        if reset:
            await _async_light_call(
                hass,
                SERVICE_TURN_ON,
                lights,
                {ATTR_BRIGHTNESS: BRIGHTNESS_START, ATTR_TRANSITION: 0},
            )
        await _async_light_call(
            hass,
            SERVICE_TURN_ON,
            lights,
            {ATTR_BRIGHTNESS: BRIGHTNESS_FULL, ATTR_TRANSITION: ramp_seconds},
        )
    except HomeAssistantError as exception:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="ramp_failed",
        ) from exception


async def async_stop_ramp(hass: HomeAssistant, lights: Sequence[str]) -> None:
    """
    Turn the lights off, so the next ramp starts from zero again.

    Raises:
        HomeAssistantError: If a light rejected the call.

    """
    if not lights:
        return

    try:
        await _async_light_call(hass, SERVICE_TURN_OFF, lights, {ATTR_TRANSITION: 0})
    except HomeAssistantError as exception:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="ramp_stop_failed",
        ) from exception


async def _async_light_call(
    hass: HomeAssistant,
    service: str,
    lights: Sequence[str],
    data: dict[str, int],
) -> None:
    """Call one light service for every configured target."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        service,
        {ATTR_ENTITY_ID: list(lights), **data},
        blocking=True,
    )
