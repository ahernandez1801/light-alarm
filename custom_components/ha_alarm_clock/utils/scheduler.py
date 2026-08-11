"""Timer management for ha_alarm_clock — when each alarm rings, and what leads up to it."""

from datetime import timedelta
from functools import partial
from typing import TYPE_CHECKING

from custom_components.ha_alarm_clock.const import (
    CONF_ALARM_TIME,
    CONF_LIGHTS,
    CONF_RAMP_MINUTES,
    CONF_SNOOZE_MINUTES,
    DEFAULT_RAMP_MINUTES,
    DEFAULT_SNOOZE_MINUTES,
    LOGGER,
    AlarmPhase,
)
from custom_components.ha_alarm_clock.utils.ramp import async_start_ramp, async_stop_ramp
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from datetime import datetime

    from custom_components.ha_alarm_clock.coordinator import SunriseAlarmDataUpdateCoordinator
    from custom_components.ha_alarm_clock.utils.audio import AlarmAudio
    from custom_components.ha_alarm_clock.utils.notifier import AlarmNotifier
    from homeassistant.config_entries import ConfigSubentry
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant

MIN_RAMP_SECONDS = 1


class AlarmScheduler:
    """
    Own the timers for every alarm subentry.

    The configured time is when the alarm **rings**. The sunrise runs up to it, so the
    lights start at `alarm time - sunrise length` and reach full exactly as the ringing
    begins — waking to a lit room rather than to a room that starts brightening once it
    is already too late.

    One alarm holds the wake-up cycle at a time: an alarm whose sunrise is due while
    another is ramping, ringing or snoozed is skipped for that day. Whichever timer Home
    Assistant runs first wins, which for two alarms set to the same minute is the one
    armed first.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: SunriseAlarmDataUpdateCoordinator,
        notifier: AlarmNotifier,
        audio: AlarmAudio,
    ) -> None:
        """Initialize the scheduler."""
        self._hass = hass
        self._coordinator = coordinator
        self._notifier = notifier
        self._audio = audio
        self._timers: dict[str, CALLBACK_TYPE] = {}
        self._ring_at: dict[str, datetime] = {}

    @callback
    def async_start(self) -> None:
        """
        Arm every configured alarm, resuming any wake-up that a restart interrupted.

        Without the resume, a restart mid-sunrise would leave the lights at whatever
        brightness they had reached with nothing left to dismiss.
        """
        entry = self._coordinator.config_entry

        for subentry_id in entry.subentries:
            state = self._coordinator.async_state_for(subentry_id)

            if state is not None and state.enabled and state.phase is not AlarmPhase.IDLE:
                entry.async_create_task(
                    self._hass,
                    self._async_resume(subentry_id),
                    name=f"{subentry_id} resume",
                )
                continue

            self.async_rearm(subentry_id)

    @callback
    def async_stop(self) -> None:
        """Cancel every pending timer."""
        for cancel in self._timers.values():
            cancel()
        self._timers.clear()
        self._ring_at.clear()
        self._notifier.async_shutdown()
        self._audio.async_shutdown()

    @callback
    def async_rearm(self, subentry_id: str) -> None:
        """
        Drop whatever was scheduled for one alarm and schedule its next ring.

        Everything the old time had pending is cancelled first, so an edited alarm has
        exactly one cycle armed and never fires on yesterday's setting.
        """
        self._async_cancel(subentry_id)

        state = self._coordinator.async_state_for(subentry_id)
        if state is None or not state.enabled:
            self._coordinator.async_update_phase(subentry_id, AlarmPhase.IDLE, None)
            return

        ring_at = self._async_next_ring(subentry_id)
        if ring_at is None:
            self._coordinator.async_update_phase(subentry_id, AlarmPhase.IDLE, None)
            return

        self._async_arm(subentry_id, ring_at, AlarmPhase.IDLE)

    @callback
    def async_reconfigure(self, subentry_id: str) -> None:
        """
        Pick up an edited alarm time or duration.

        An alarm that is mid-wake-up is left alone: changing tomorrow's time should not
        cancel the sunrise happening right now. Its next cycle uses the new time.
        """
        state = self._coordinator.async_state_for(subentry_id)
        if state is None or state.phase is not AlarmPhase.IDLE:
            return

        self.async_rearm(subentry_id)

    async def async_disarm(self, subentry_id: str) -> None:
        """Clear any notification and audio for one alarm and schedule its next ring."""
        await self._notifier.async_stop(subentry_id)
        await self._audio.async_stop(subentry_id)
        self.async_rearm(subentry_id)

    async def async_snooze(self, subentry_id: str) -> None:
        """
        Stop the current wake-up and start it again after the alarm's snooze time.

        The sunrise restarts from dark and is compressed to fit the snooze, so the
        lights are back at full when the alarm rings again.
        """
        state = self._coordinator.async_state_for(subentry_id)
        if state is None or state.phase is AlarmPhase.IDLE:
            return

        self._async_cancel(subentry_id)
        await self._notifier.async_stop(subentry_id)
        await self._audio.async_stop(subentry_id)
        await async_stop_ramp(self._hass, self._async_lights(subentry_id))

        minutes = self._async_option(subentry_id, CONF_SNOOZE_MINUTES, DEFAULT_SNOOZE_MINUTES)
        self._async_arm(subentry_id, dt_util.now() + timedelta(minutes=minutes), AlarmPhase.SNOOZED)

    async def async_dismiss(self, subentry_id: str) -> None:
        """
        End the current wake-up.

        The lights are left as they are — the point of the sunrise is that they are on
        once the user is awake. A one-time alarm disarms itself here.
        """
        state = self._coordinator.async_state_for(subentry_id)
        if state is None or state.phase is AlarmPhase.IDLE:
            return

        self._async_cancel(subentry_id)
        await self._notifier.async_stop(subentry_id)
        await self._audio.async_stop(subentry_id)
        self._coordinator.async_update_phase(subentry_id, AlarmPhase.IDLE, None)

        if state.one_time:
            await self._coordinator.async_set_enabled(subentry_id, enabled=False)
        else:
            self.async_rearm(subentry_id)

    @callback
    def _async_arm(self, subentry_id: str, ring_at: datetime, phase: AlarmPhase) -> None:
        """Schedule the sunrise that leads up to one ring, and the ring itself."""
        self._ring_at[subentry_id] = ring_at

        ramp_minutes = self._async_option(subentry_id, CONF_RAMP_MINUTES, DEFAULT_RAMP_MINUTES)
        starts_at = max(ring_at - timedelta(minutes=ramp_minutes), dt_util.now())

        self._async_schedule(subentry_id, starts_at, self._async_begin_ramp)
        self._coordinator.async_update_phase(subentry_id, phase, ring_at)

    async def _async_begin_ramp(self, subentry_id: str, _now: datetime, *, reset: bool = True) -> None:
        """Take the lights from dark to full, arriving there as the alarm rings."""
        if self._coordinator.async_any_active(excluding=subentry_id):
            LOGGER.info("Skipping alarm %s: another alarm is already active", subentry_id)
            self.async_rearm(subentry_id)
            return

        ring_at = self._ring_at.get(subentry_id)
        if ring_at is None:
            return

        seconds = max(MIN_RAMP_SECONDS, int((ring_at - dt_util.now()).total_seconds()))

        self._coordinator.async_update_phase(subentry_id, AlarmPhase.RAMPING, ring_at)
        self._async_schedule(subentry_id, ring_at, self._async_ring)

        try:
            await async_start_ramp(self._hass, self._async_lights(subentry_id), seconds, reset=reset)
        except HomeAssistantError:
            LOGGER.exception("Could not start the sunrise for alarm %s", subentry_id)

    async def _async_ring(self, subentry_id: str, _now: datetime) -> None:
        """Ring, and put a way to stop it in front of the user."""
        self._timers.pop(subentry_id, None)
        self._coordinator.async_update_phase(subentry_id, AlarmPhase.RINGING, None)
        await self._notifier.async_start(subentry_id)
        await self._audio.async_start(subentry_id)

    async def _async_resume(self, subentry_id: str) -> None:
        """Pick a wake-up back up where a Home Assistant restart interrupted it."""
        state = self._coordinator.async_state_for(subentry_id)
        if state is None:
            return

        now = dt_util.now()
        ring_at = state.next_fire

        if state.phase is AlarmPhase.RINGING or ring_at is None or ring_at <= now:
            await self._async_ring(subentry_id, now)
            return

        self._ring_at[subentry_id] = ring_at

        if state.phase is AlarmPhase.RAMPING:
            await self._async_begin_ramp(subentry_id, now, reset=False)
        else:
            self._async_arm(subentry_id, ring_at, state.phase)

    @callback
    def _async_schedule(
        self,
        subentry_id: str,
        target: datetime,
        action: object,
    ) -> None:
        """Replace the pending timer for one alarm."""
        self._async_cancel(subentry_id, keep_cycle=True)
        self._timers[subentry_id] = async_track_point_in_time(
            self._hass,
            partial(action, subentry_id),  # type: ignore[operator] - Every action here takes (subentry_id, now).
            target,
        )

    @callback
    def _async_cancel(self, subentry_id: str, *, keep_cycle: bool = False) -> None:
        """Cancel the pending timer for one alarm, if there is one."""
        cancel = self._timers.pop(subentry_id, None)
        if cancel is not None:
            cancel()

        if not keep_cycle:
            self._ring_at.pop(subentry_id, None)

    @callback
    def _async_next_ring(self, subentry_id: str) -> datetime | None:
        """
        Return when this alarm next rings, in local time.

        Returns:
            Today's alarm time while it is still ahead, otherwise tomorrow's; None when
            the subentry has no usable time.

        """
        subentry = self._async_subentry(subentry_id)
        if subentry is None:
            return None

        alarm_time = dt_util.parse_time(str(subentry.data.get(CONF_ALARM_TIME, "")))
        if alarm_time is None:
            LOGGER.warning("Alarm %s has no valid time configured", subentry_id)
            return None

        now = dt_util.now()
        target = now.replace(
            hour=alarm_time.hour,
            minute=alarm_time.minute,
            second=alarm_time.second,
            microsecond=0,
        )
        if target <= now:
            target += timedelta(days=1)

        return target

    @callback
    def _async_lights(self, subentry_id: str) -> list[str]:
        """
        Return the light entities this alarm drives.

        Returns:
            The configured light entity IDs.

        """
        subentry = self._async_subentry(subentry_id)
        if subentry is None:
            return []

        return list(subentry.data.get(CONF_LIGHTS, []))

    @callback
    def _async_option(self, subentry_id: str, key: str, default: int) -> int:
        """
        Return one numeric setting of an alarm.

        Returns:
            The configured value, or the default for an alarm created before the field.

        """
        subentry = self._async_subentry(subentry_id)
        if subentry is None:
            return default

        return int(subentry.data.get(key, default))

    @callback
    def _async_subentry(self, subentry_id: str) -> ConfigSubentry | None:
        """
        Return the subentry backing one alarm.

        Returns:
            The subentry, or None when it has been deleted.

        """
        return self._coordinator.config_entry.subentries.get(subentry_id)
