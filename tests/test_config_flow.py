"""Config flow and subentry flow tests for ha_alarm_clock."""

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ha_alarm_clock.config_flow_handler.schemas import to_form_data
from custom_components.ha_alarm_clock.const import CONF_ALARM_TIME, DOMAIN, SUBENTRY_TYPE_ALARM
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import ALARM_DATA, ALARM_NAME


async def test_user_flow_creates_entry_with_first_alarm(hass: HomeAssistant) -> None:
    """The setup dialog collects one alarm and stores it as the entry's first subentry."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], to_form_data(ALARM_DATA))
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {}

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    subentry = next(iter(entry.subentries.values()))
    assert subentry.subentry_type == SUBENTRY_TYPE_ALARM
    assert subentry.title == ALARM_NAME
    assert subentry.data[CONF_ALARM_TIME] == ALARM_DATA[CONF_ALARM_TIME]


async def test_single_entry_only(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """A second setup attempt aborts, because alarms are added as subentries instead."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_subentry_flow_adds_second_alarm(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """The add-alarm dialog creates another subentry on the existing entry."""
    result = await hass.config_entries.subentries.async_init(
        (init_integration.entry_id, SUBENTRY_TYPE_ALARM),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM

    second = {**ALARM_DATA, CONF_NAME: "Weekend", CONF_ALARM_TIME: "09:30:00"}
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], to_form_data(second))
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(init_integration.subentries) == 2
    assert hass.states.get("sensor.weekend_next_alarm") is not None
