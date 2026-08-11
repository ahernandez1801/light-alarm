"""Alarm state coordinator for ha_alarm_clock."""

from typing import TYPE_CHECKING, Any

from custom_components.ha_alarm_clock.const import (
    ATTR_ALARM_ENABLED,
    ATTR_ALARM_NEXT_FIRE,
    ATTR_ALARM_ONE_TIME,
    ATTR_ALARM_PHASE,
    DOMAIN,
    LOGGER,
    STORAGE_KEY,
    STORAGE_VERSION,
    AlarmPhase,
)
from custom_components.ha_alarm_clock.data import AlarmState
from homeassistant.core import callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from datetime import datetime

    from custom_components.ha_alarm_clock.data import SunriseAlarmConfigEntry
    from custom_components.ha_alarm_clock.utils.scheduler import AlarmScheduler
    from homeassistant.core import HomeAssistant

type StoredState = dict[str, dict[str, Any]]

SAVE_DELAY_SECONDS = 5


class SunriseAlarmDataUpdateCoordinator(DataUpdateCoordinator[dict[str, AlarmState]]):
    """
    Hold one `AlarmState` per alarm subentry and hand it to every entity.

    Nothing is fetched, so there is no update interval: the scheduler advances the
    state and publishes it with `async_set_updated_data`.
    """

    config_entry: SunriseAlarmConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: SunriseAlarmConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=None,
        )
        self._store = Store[StoredState](hass, STORAGE_VERSION, STORAGE_KEY)
        self._states: dict[str, AlarmState] = {}
        self.scheduler: AlarmScheduler | None = None

    async def async_load(self) -> None:
        """
        Rebuild the alarm states from the subentries and what was persisted.

        The phase is restored as well as the switch positions, so a restart in the
        middle of a wake-up leaves the user something to snooze or dismiss instead of
        lights nobody can turn off from the integration.
        """
        stored = await self._store.async_load() or {}

        self._states = {
            subentry_id: _restore(stored.get(subentry_id, {})) for subentry_id in self.config_entry.subentries
        }

    async def _async_update_data(self) -> dict[str, AlarmState]:
        """
        Return the current alarm states.

        Returns:
            A snapshot of every alarm's state, keyed by subentry ID.

        """
        return dict(self._states)

    @callback
    def async_state_for(self, subentry_id: str) -> AlarmState | None:
        """
        Return the state of one alarm.

        Returns:
            The alarm's state, or None when the subentry is gone.

        """
        return self._states.get(subentry_id)

    async def async_set_enabled(self, subentry_id: str, *, enabled: bool) -> None:
        """Arm or disarm one alarm, persist the choice and re-arm its timer."""
        await self._async_write(subentry_id, enabled=enabled)
        if self.scheduler is not None:
            await self.scheduler.async_disarm(subentry_id)

    @callback
    def async_update_alarm_config(self, subentry_id: str, changes: dict[str, Any]) -> None:
        """
        Write changed settings back to the alarm's subentry.

        This is the path the `time` and `number` entities take, so an alarm can be
        adjusted from a dashboard rather than only through its dialog. The entry's
        update listener re-arms the alarm; it does not reload, so a wake-up in progress
        survives the edit.
        """
        subentry = self.config_entry.subentries.get(subentry_id)
        if subentry is None:
            return

        self.hass.config_entries.async_update_subentry(
            self.config_entry,
            subentry,
            data={**subentry.data, **changes},
        )

    async def async_set_one_time(self, subentry_id: str, *, one_time: bool) -> None:
        """Make one alarm fire once, or every day, and persist the choice."""
        await self._async_write(subentry_id, one_time=one_time)

    async def _async_write(
        self,
        subentry_id: str,
        *,
        enabled: bool | None = None,
        one_time: bool | None = None,
    ) -> None:
        """Update the persisted half of an alarm's state and publish it."""
        current = self._states.get(subentry_id)
        if current is None:
            LOGGER.debug("Ignoring a state change for unknown alarm %s", subentry_id)
            return

        self._states[subentry_id] = AlarmState(
            enabled=current.enabled if enabled is None else enabled,
            one_time=current.one_time if one_time is None else one_time,
            phase=current.phase,
            next_fire=current.next_fire,
        )
        self._store.async_delay_save(self._data_to_store, SAVE_DELAY_SECONDS)
        self.async_set_updated_data(dict(self._states))

    @callback
    def async_update_phase(
        self,
        subentry_id: str,
        phase: AlarmPhase,
        next_fire: datetime | None,
    ) -> None:
        """Record where one alarm is in its wake-up cycle and publish it."""
        current = self._states.get(subentry_id)
        if current is None:
            return

        self._states[subentry_id] = current.with_phase(phase, next_fire)
        self._store.async_delay_save(self._data_to_store, SAVE_DELAY_SECONDS)
        self.async_set_updated_data(dict(self._states))

    @callback
    def async_any_active(self, *, excluding: str) -> bool:
        """
        Report whether another alarm is already ramping, ringing or snoozed.

        Returns:
            True when some other alarm holds the wake-up cycle.

        """
        return any(
            state.phase is not AlarmPhase.IDLE
            for subentry_id, state in self._states.items()
            if subentry_id != excluding
        )

    @callback
    def _data_to_store(self) -> StoredState:
        """
        Return the half of the alarm states that survives a restart.

        Returns:
            The persisted switch positions, keyed by subentry ID.

        """
        return {
            subentry_id: {
                ATTR_ALARM_ENABLED: state.enabled,
                ATTR_ALARM_ONE_TIME: state.one_time,
                ATTR_ALARM_PHASE: str(state.phase),
                ATTR_ALARM_NEXT_FIRE: state.next_fire.isoformat() if state.next_fire else None,
            }
            for subentry_id, state in self._states.items()
        }


def _restore(stored: dict[str, Any]) -> AlarmState:
    """
    Rebuild one alarm state from its persisted form.

    Returns:
        The restored state; a stored phase that is no longer a known one falls back to
        idle rather than failing the whole setup.

    """
    try:
        phase = AlarmPhase(stored.get(ATTR_ALARM_PHASE, AlarmPhase.IDLE))
    except ValueError:
        phase = AlarmPhase.IDLE

    raw_next_fire = stored.get(ATTR_ALARM_NEXT_FIRE)

    return AlarmState(
        enabled=bool(stored.get(ATTR_ALARM_ENABLED, True)),
        one_time=bool(stored.get(ATTR_ALARM_ONE_TIME, False)),
        phase=phase,
        next_fire=dt_util.parse_datetime(raw_next_fire) if raw_next_fire else None,
    )
