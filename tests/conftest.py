"""
Shared fixtures for the ha_alarm_clock tests.

Test modules may not import one another — Ruff bans importing `tests`, which a relative
import between test files resolves to. Anything shared therefore arrives as a fixture.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.ha_alarm_clock.const import (
    CONF_ALARM_TIME,
    CONF_LIGHTS,
    CONF_RAMP_MINUTES,
    CONF_SNOOZE_MINUTES,
    DOMAIN,
    SUBENTRY_TYPE_ALARM,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

ALARM_NAME = "Weekday"
ALARM_LIGHT = "light.bedroom"

# Entity IDs are "<device> <alarm> <entity>": every alarm lives on the single
# Sunrise Alarm device, and its name reaches the entity through a placeholder.
ALARM_SLUG = "sunrise_alarm_weekday"

RAMP_MINUTES = 15
SNOOZE_MINUTES = 9

STORE_FLUSH_SECONDS = 10

# 02:00 in the US/Pacific zone the test harness configures — hours away from the 07:00
# alarm in either direction, so no test starts inside a sunrise.
FROZEN_START = "2026-01-01 10:00:00+00:00"

ALARM_DATA: dict[str, Any] = {
    CONF_NAME: ALARM_NAME,
    CONF_ALARM_TIME: "07:00:00",
    CONF_LIGHTS: [ALARM_LIGHT],
    CONF_RAMP_MINUTES: RAMP_MINUTES,
    CONF_SNOOZE_MINUTES: SNOOZE_MINUTES,
}


@dataclass(frozen=True)
class AlarmEntities:
    """The entity IDs of the alarm every test works with."""

    next_alarm: str = f"sensor.{ALARM_SLUG}_next_alarm"
    ringing: str = f"binary_sensor.{ALARM_SLUG}_ringing"
    alarm: str = f"switch.{ALARM_SLUG}_alarm"
    one_time: str = f"switch.{ALARM_SLUG}_only_once"
    snooze: str = f"button.{ALARM_SLUG}_snooze"
    dismiss: str = f"button.{ALARM_SLUG}_dismiss"
    alarm_time: str = f"time.{ALARM_SLUG}_alarm_time"
    sunrise_length: str = f"number.{ALARM_SLUG}_sunrise_length"
    snooze_length: str = f"number.{ALARM_SLUG}_snooze_length"


@dataclass
class AlarmCycle:
    """Drives one alarm through its wake-up cycle by moving the frozen clock."""

    hass: HomeAssistant
    freezer: FrozenDateTimeFactory
    entities: AlarmEntities
    ramp_minutes: int = RAMP_MINUTES

    def next_ring(self) -> datetime:
        """
        Return when the alarm is due to ring, in Home Assistant's local time.

        The sensor is a UTC timestamp, so the value is converted back — an alarm set to
        07:00 is only 07:00 in the local zone.

        Returns:
            The next-alarm sensor's value, as local time.

        """
        state = self.hass.states.get(self.entities.next_alarm)
        assert state is not None

        return dt_util.as_local(datetime.fromisoformat(state.state))

    async def move_to(self, target: datetime) -> None:
        """Move the clock to a point in time and let any timer there run."""
        self.freezer.move_to(target)
        async_fire_time_changed(self.hass, target)
        await self.hass.async_block_till_done()

    async def advance(self, seconds: int) -> None:
        """Move the clock forward from wherever it is now."""
        await self.move_to(dt_util.now() + timedelta(seconds=seconds))

    async def start_sunrise(self) -> datetime:
        """
        Move to the start of the sunrise, one sunrise length before the ring.

        Returns:
            The time the alarm is due to ring.

        """
        ring_at = self.next_ring()
        await self.move_to(ring_at - timedelta(minutes=self.ramp_minutes))

        return ring_at

    async def reach_ringing(self) -> datetime:
        """
        Run a whole cycle, from the start of the sunrise to the alarm ringing.

        Returns:
            The time the alarm rang.

        """
        ring_at = await self.start_sunrise()
        await self.move_to(ring_at)

        return ring_at

    async def flush_store(self) -> None:
        """Run the clock past the coordinator's delayed save, so the state is on disk."""
        await self.advance(STORE_FLUSH_SECONDS)

    async def press(self, entity_id: str) -> None:
        """Press one of the alarm's buttons."""
        await self.hass.services.async_call("button", "press", {ATTR_ENTITY_ID: entity_id}, blocking=True)
        await self.hass.async_block_till_done()


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom integrations in every test."""


@pytest.fixture(autouse=True)
def frozen_clock(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    """
    Pin the clock well clear of the alarm before anything is set up.

    Without this the suite runs against the real wall clock, and every test started
    within a sunrise length of 07:00 in Home Assistant's test timezone would begin its
    sunrise during setup. That failed ten tests exactly once a day.

    Returns:
        The frozen clock, now at a deterministic instant.

    """
    freezer.move_to(FROZEN_START)
    return freezer


@pytest.fixture
def alarm_data() -> dict[str, Any]:
    """
    Return the configuration of the alarm every test works with.

    Returns:
        A fresh copy, so a test may extend it without affecting the next one.

    """
    return dict(ALARM_DATA)


@pytest.fixture
def entities() -> AlarmEntities:
    """
    Return the alarm's entity IDs.

    Returns:
        The entity IDs derived from the alarm's name.

    """
    return AlarmEntities()


@pytest.fixture
def cycle(hass: HomeAssistant, freezer: FrozenDateTimeFactory, entities: AlarmEntities) -> AlarmCycle:
    """
    Return the helper that walks the alarm through a wake-up.

    Returns:
        A cycle bound to this test's Home Assistant and frozen clock.

    """
    return AlarmCycle(hass, freezer, entities)


@pytest.fixture
def config_entry(alarm_data: dict[str, Any]) -> MockConfigEntry:
    """
    Return a config entry holding one alarm.

    Returns:
        An unloaded config entry with a single alarm subentry.

    """
    return MockConfigEntry(
        domain=DOMAIN,
        title="Sunrise Alarm",
        data={},
        subentries_data=[
            ConfigSubentryData(
                data=alarm_data,
                subentry_type=SUBENTRY_TYPE_ALARM,
                title=ALARM_NAME,
                unique_id=None,
            ),
        ],
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    frozen_clock: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """
    Set up the integration from a config entry.

    Returns:
        The config entry, now loaded.

    """
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


@pytest.fixture
def setup_with_data(
    hass: HomeAssistant,
    frozen_clock: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
) -> Any:
    """
    Return a callable that sets the integration up with a modified alarm.

    Returns:
        An async callable taking the alarm's configuration data.

    """

    async def _setup(data: dict[str, Any]) -> MockConfigEntry:
        config_entry.add_to_hass(hass)
        subentry_id = next(iter(config_entry.subentries))
        hass.config_entries.async_update_subentry(
            config_entry,
            config_entry.subentries[subentry_id],
            data=data,
        )
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        return config_entry

    return _setup
