"""
Notifications that keep a ringing alarm reachable.

The button entities and the service actions are always available, but both assume the
user is already at a dashboard or has wired a physical button. These notifications are
the path that comes to them instead: a persistent notification in every Home Assistant
UI, and — when the alarm has notification targets configured — an actionable
notification on the phone, re-sent while the alarm is still ringing so that swiping one
away does not remove the last way to stop it.
"""

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from custom_components.ha_alarm_clock.const import (
    ACTION_DISMISS_PREFIX,
    ACTION_SNOOZE_PREFIX,
    CONF_NOTIFY_TARGETS,
    CONF_PHONE_CRITICAL_SOUND,
    DOMAIN,
    EVENT_MOBILE_APP_ACTION,
    LOGGER,
    NOTIFY_ACTION_DISMISS_TITLE,
    NOTIFY_ACTION_SNOOZE_TITLE,
    NOTIFY_CLEAR_MESSAGE,
    NOTIFY_CRITICAL_VOLUME,
    NOTIFY_DOMAIN,
    NOTIFY_MESSAGE,
    NOTIFY_REPEAT_MINUTES,
    NOTIFY_TITLE,
)
from homeassistant.components import persistent_notification
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval

if TYPE_CHECKING:
    from datetime import datetime

    from custom_components.ha_alarm_clock.coordinator import SunriseAlarmDataUpdateCoordinator
    from custom_components.ha_alarm_clock.utils.scheduler import AlarmScheduler
    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant

ATTR_ACTION = "action"


class AlarmNotifier:
    """Send, repeat and clear the notifications for a ringing alarm."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: SunriseAlarmDataUpdateCoordinator,
    ) -> None:
        """Initialize the notifier."""
        self._hass = hass
        self._coordinator = coordinator
        self._repeats: dict[str, CALLBACK_TYPE] = {}

    async def async_start(self, subentry_id: str) -> None:
        """Notify that an alarm is ringing, and keep re-notifying until it is stopped."""
        await self._async_send(subentry_id)

        self._async_cancel_repeat(subentry_id)
        self._repeats[subentry_id] = async_track_time_interval(
            self._hass,
            self._async_repeat(subentry_id),
            timedelta(minutes=NOTIFY_REPEAT_MINUTES),
        )

    async def async_stop(self, subentry_id: str) -> None:
        """Stop repeating and clear the notifications for one alarm."""
        self._async_cancel_repeat(subentry_id)

        persistent_notification.async_dismiss(self._hass, self._notification_id(subentry_id))

        for service in self._async_targets(subentry_id):
            await self._async_notify(
                service,
                {
                    "message": NOTIFY_CLEAR_MESSAGE,
                    "data": {"tag": self._notification_id(subentry_id)},
                },
            )

    @callback
    def async_shutdown(self) -> None:
        """Cancel every repeat timer, without touching the notifications themselves."""
        for cancel in self._repeats.values():
            cancel()
        self._repeats.clear()

    def _async_repeat(self, subentry_id: str) -> Any:
        """
        Build the interval callback that re-sends one alarm's notification.

        Returns:
            A coroutine function taking the current time.

        """

        async def _repeat(_now: datetime) -> None:
            await self._async_send(subentry_id)

        return _repeat

    async def _async_send(self, subentry_id: str) -> None:
        """Send the persistent notification and every configured phone notification."""
        name = self._async_name(subentry_id)
        message = NOTIFY_MESSAGE.format(name=name)
        tag = self._notification_id(subentry_id)

        persistent_notification.async_create(
            self._hass,
            message,
            title=NOTIFY_TITLE,
            notification_id=tag,
        )

        data: dict[str, Any] = {
            "tag": tag,
            "persistent": True,
            "sticky": True,
            "channel": NOTIFY_TITLE,
            "importance": "high",
            "ttl": 0,
            "priority": "high",
            "actions": [
                {
                    "action": f"{ACTION_SNOOZE_PREFIX}{subentry_id}",
                    "title": NOTIFY_ACTION_SNOOZE_TITLE,
                },
                {
                    "action": f"{ACTION_DISMISS_PREFIX}{subentry_id}",
                    "title": NOTIFY_ACTION_DISMISS_TITLE,
                },
            ],
        }

        if self._async_critical_sound(subentry_id):
            data["push"] = {
                "sound": {"name": "default", "critical": 1, "volume": NOTIFY_CRITICAL_VOLUME},
            }

        for service in self._async_targets(subentry_id):
            await self._async_notify(
                service,
                {
                    "title": NOTIFY_TITLE,
                    "message": message,
                    "data": data,
                },
            )

    async def _async_notify(self, service: str, data: dict[str, Any]) -> None:
        """Call one notify service, treating its failure as non-fatal."""
        try:
            await self._hass.services.async_call(NOTIFY_DOMAIN, service, data, blocking=True)
        except (HomeAssistantError, vol.Invalid) as exception:
            LOGGER.warning("Could not notify through %s.%s: %s", NOTIFY_DOMAIN, service, exception)

    @callback
    def _async_critical_sound(self, subentry_id: str) -> bool:
        """
        Return whether this alarm's phone notification may break through silent mode.

        Returns:
            The configured consent, defaulting to on for alarms predating the field.

        """
        subentry = self._coordinator.config_entry.subentries.get(subentry_id)
        if subentry is None:
            return False

        return bool(subentry.data.get(CONF_PHONE_CRITICAL_SOUND, True))

    @callback
    def _async_targets(self, subentry_id: str) -> list[str]:
        """
        Return the notify services this alarm sends to.

        Returns:
            The configured notify service names, without their domain.

        """
        subentry = self._coordinator.config_entry.subentries.get(subentry_id)
        if subentry is None:
            return []

        return list(subentry.data.get(CONF_NOTIFY_TARGETS, []))

    @callback
    def _async_name(self, subentry_id: str) -> str:
        """
        Return the alarm's name for the notification text.

        Returns:
            The subentry title, or the integration title when it is gone.

        """
        subentry = self._coordinator.config_entry.subentries.get(subentry_id)
        return subentry.title if subentry is not None else self._coordinator.config_entry.title

    @callback
    def _async_cancel_repeat(self, subentry_id: str) -> None:
        """Cancel the repeat timer for one alarm, if there is one."""
        cancel = self._repeats.pop(subentry_id, None)
        if cancel is not None:
            cancel()

    @callback
    def _notification_id(self, subentry_id: str) -> str:
        """
        Return the ID that both notification channels use for one alarm.

        Returns:
            An ID unique to this alarm, so a repeat replaces rather than stacks.

        """
        return f"{DOMAIN}_{subentry_id}"


@callback
def async_setup_action_listener(
    hass: HomeAssistant,
    scheduler: AlarmScheduler,
) -> CALLBACK_TYPE:
    """
    Listen for the companion app's notification actions.

    Returns:
        The callback that removes the listener.

    """

    async def _handle(event: Event) -> None:
        action = str(event.data.get(ATTR_ACTION, ""))

        if action.startswith(ACTION_SNOOZE_PREFIX):
            await scheduler.async_snooze(action.removeprefix(ACTION_SNOOZE_PREFIX))
        elif action.startswith(ACTION_DISMISS_PREFIX):
            await scheduler.async_dismiss(action.removeprefix(ACTION_DISMISS_PREFIX))

    return hass.bus.async_listen(EVENT_MOBILE_APP_ACTION, _handle)
