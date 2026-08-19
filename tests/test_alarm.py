"""Wake-up cycle tests for ha_alarm_clock — the sunrise, the ring, snoozing and dismissing."""

from datetime import timedelta
from typing import Any

from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.ha_alarm_clock.const import (
    ACTION_DISMISS_PREFIX,
    ACTION_SNOOZE_PREFIX,
    CONF_GATE_ENTITY,
    CONF_GATE_STATE,
    CONF_NOTIFY_TARGETS,
    CONF_RAMP_MINUTES,
    DOMAIN,
    EVENT_MOBILE_APP_ACTION,
    NOTIFY_DOMAIN,
)
from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_TRANSITION, DOMAIN as LIGHT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import RAMP_MINUTES, SNOOZE_MINUTES, AlarmCycle, AlarmEntities

NOTIFY_SERVICE = "mobile_app_test"
GATE_ENTITY = "person.tester"


async def test_entities_created_per_alarm(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entities: AlarmEntities,
) -> None:
    """Every alarm gets its own switches, buttons, editable settings and sensors."""
    assert hass.states.get(entities.alarm).state == STATE_ON
    assert hass.states.get(entities.one_time).state == STATE_OFF
    assert hass.states.get(entities.ringing).state == STATE_OFF
    assert hass.states.get(entities.next_alarm).state != STATE_UNKNOWN
    assert hass.states.get(entities.snooze) is not None
    assert hass.states.get(entities.dismiss) is not None
    assert hass.states.get(entities.alarm_time).state == "07:00:00"
    assert hass.states.get(entities.sunrise_length).state == "15.0"
    assert hass.states.get(entities.snooze_length).state == "9.0"


async def test_next_alarm_is_the_ring_time(
    init_integration: MockConfigEntry,
    cycle: AlarmCycle,
) -> None:
    """The sensor reports when the alarm rings, not when its sunrise starts."""
    ring_at = cycle.next_ring()

    assert (ring_at.hour, ring_at.minute) == (7, 0)


async def test_sunrise_finishes_as_the_alarm_rings(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    cycle: AlarmCycle,
    entities: AlarmEntities,
) -> None:
    """The lights start a sunrise length early and reach full exactly at the alarm time."""
    turn_on = async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_ON)

    ring_at = await cycle.start_sunrise()

    assert len(turn_on) == 2
    assert turn_on[0].data[ATTR_BRIGHTNESS] == 1
    assert turn_on[1].data[ATTR_BRIGHTNESS] == 255
    assert turn_on[1].data[ATTR_TRANSITION] == RAMP_MINUTES * 60
    assert hass.states.get(entities.ringing).state == STATE_OFF

    await cycle.move_to(ring_at)

    assert hass.states.get(entities.ringing).state == STATE_ON


async def test_snooze_turns_the_lights_off_and_reschedules(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    cycle: AlarmCycle,
    entities: AlarmEntities,
) -> None:
    """A snooze ends the sunrise and starts a new one, ringing after the snooze length."""
    async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_ON)
    turn_off = async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_OFF)

    await cycle.reach_ringing()
    await cycle.press(entities.snooze)

    assert len(turn_off) == 1
    assert hass.states.get(entities.ringing).state == STATE_OFF
    assert cycle.next_ring() - dt_util.now() <= timedelta(minutes=SNOOZE_MINUTES)


async def test_dismiss_leaves_the_lights_on(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    cycle: AlarmCycle,
    entities: AlarmEntities,
) -> None:
    """Dismissing ends the wake-up and arms the alarm for the next day."""
    async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_ON)
    turn_off = async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_OFF)

    rang_at = await cycle.reach_ringing()
    await cycle.press(entities.dismiss)

    assert turn_off == []
    assert hass.states.get(entities.ringing).state == STATE_OFF
    assert cycle.next_ring() > rang_at


async def test_one_time_alarm_disarms_itself(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    cycle: AlarmCycle,
    entities: AlarmEntities,
) -> None:
    """An alarm set to fire only once turns itself off when it is dismissed."""
    async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_ON)
    async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_OFF)

    await hass.services.async_call(
        "switch",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entities.one_time},
        blocking=True,
    )
    await cycle.reach_ringing()
    await cycle.press(entities.dismiss)

    assert hass.states.get(entities.alarm).state == STATE_OFF
    assert hass.states.get(entities.next_alarm).state == STATE_UNKNOWN


async def test_ringing_survives_a_restart(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    cycle: AlarmCycle,
    entities: AlarmEntities,
) -> None:
    """A reload while an alarm rings leaves it ringing, so it can still be dismissed."""
    async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_ON)

    await cycle.reach_ringing()
    await cycle.flush_store()

    await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entities.ringing).state == STATE_ON


async def test_notification_offers_snooze_and_dismiss(
    hass: HomeAssistant,
    alarm_data: dict[str, Any],
    setup_with_data: Any,
    cycle: AlarmCycle,
    entities: AlarmEntities,
) -> None:
    """A configured phone gets an actionable notification, and its action snoozes."""
    async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_ON)
    async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_OFF)
    notifications = async_mock_service(hass, NOTIFY_DOMAIN, NOTIFY_SERVICE)

    entry = await setup_with_data({**alarm_data, CONF_NOTIFY_TARGETS: [NOTIFY_SERVICE]})
    subentry_id = next(iter(entry.subentries))

    await cycle.reach_ringing()

    assert len(notifications) == 1
    actions = notifications[0].data["data"]["actions"]
    assert [action["action"] for action in actions] == [
        f"{ACTION_SNOOZE_PREFIX}{subentry_id}",
        f"{ACTION_DISMISS_PREFIX}{subentry_id}",
    ]

    hass.bus.async_fire(EVENT_MOBILE_APP_ACTION, {"action": f"{ACTION_SNOOZE_PREFIX}{subentry_id}"})
    await hass.async_block_till_done()

    assert hass.states.get(entities.ringing).state == STATE_OFF


async def test_alarm_time_is_editable_without_a_reload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    cycle: AlarmCycle,
    entities: AlarmEntities,
) -> None:
    """Setting the time entity replaces the old schedule with the new one."""
    before = cycle.next_ring()

    await hass.services.async_call(
        "time",
        "set_value",
        {ATTR_ENTITY_ID: entities.alarm_time, "time": "05:30:00"},
        blocking=True,
    )
    await hass.async_block_till_done()

    after = cycle.next_ring()

    assert hass.states.get(entities.alarm_time).state == "05:30:00"
    assert after != before
    assert (after.hour, after.minute) == (5, 30)


async def test_the_old_time_no_longer_fires(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    cycle: AlarmCycle,
    entities: AlarmEntities,
) -> None:
    """After an edit, nothing happens at the time the alarm used to be set to."""
    turn_on = async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_ON)
    old_ring = cycle.next_ring()

    await hass.services.async_call(
        "time",
        "set_value",
        {ATTR_ENTITY_ID: entities.alarm_time, "time": "23:45:00"},
        blocking=True,
    )
    await hass.async_block_till_done()

    await cycle.move_to(old_ring + timedelta(minutes=1))

    assert turn_on == []
    assert hass.states.get(entities.ringing).state == STATE_OFF


async def test_durations_are_editable(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entities: AlarmEntities,
) -> None:
    """The sunrise and snooze lengths can be changed from their number entities."""
    await hass.services.async_call(
        "number",
        "set_value",
        {ATTR_ENTITY_ID: entities.sunrise_length, "value": 30},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(entities.sunrise_length).state == "30.0"

    subentry = next(iter(init_integration.subentries.values()))
    assert subentry.data[CONF_RAMP_MINUTES] == 30


async def test_all_entities_share_the_integration_device(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entities: AlarmEntities,
) -> None:
    """Every entity of every alarm sits on the entry's single device."""
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, init_integration.entry_id),
        init_integration.entry_id,
    )
    assert device is not None

    entity_registry = er.async_get(hass)
    for entity_id in (entities.alarm, entities.ringing, entities.next_alarm, entities.snooze, entities.alarm_time):
        registry_entry = entity_registry.async_get(entity_id)
        assert registry_entry is not None
        assert registry_entry.device_id == device.id


async def test_gate_skips_the_alarm_for_the_day(
    hass: HomeAssistant,
    alarm_data: dict[str, Any],
    setup_with_data: Any,
    cycle: AlarmCycle,
) -> None:
    """An alarm whose gate entity is not in the required state skips its day."""
    turn_on = async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_ON)
    hass.states.async_set(GATE_ENTITY, "not_home")

    await setup_with_data({**alarm_data, CONF_GATE_ENTITY: GATE_ENTITY, CONF_GATE_STATE: "home"})

    ring_at = await cycle.start_sunrise()

    assert turn_on == []
    assert cycle.next_ring() == ring_at + timedelta(days=1)


async def test_gate_in_the_required_state_lets_the_alarm_fire(
    hass: HomeAssistant,
    alarm_data: dict[str, Any],
    setup_with_data: Any,
    cycle: AlarmCycle,
    entities: AlarmEntities,
) -> None:
    """An alarm whose gate entity is in the required state rings as normal."""
    async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_ON)
    hass.states.async_set(GATE_ENTITY, "home")

    await setup_with_data({**alarm_data, CONF_GATE_ENTITY: GATE_ENTITY, CONF_GATE_STATE: "home"})
    await cycle.reach_ringing()

    assert hass.states.get(entities.ringing).state == STATE_ON


async def test_unavailable_gate_never_blocks(
    hass: HomeAssistant,
    alarm_data: dict[str, Any],
    setup_with_data: Any,
    cycle: AlarmCycle,
    entities: AlarmEntities,
) -> None:
    """A broken presence tracker must not silently cancel a wake-up."""
    async_mock_service(hass, LIGHT_DOMAIN, SERVICE_TURN_ON)
    hass.states.async_set(GATE_ENTITY, STATE_UNAVAILABLE)

    await setup_with_data({**alarm_data, CONF_GATE_ENTITY: GATE_ENTITY, CONF_GATE_STATE: "home"})
    await cycle.reach_ringing()

    assert hass.states.get(entities.ringing).state == STATE_ON
