"""Base entity class for ha_alarm_clock."""

from typing import TYPE_CHECKING

from custom_components.ha_alarm_clock.const import DOMAIN, MANUFACTURER
from custom_components.ha_alarm_clock.coordinator import SunriseAlarmDataUpdateCoordinator
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

if TYPE_CHECKING:
    from custom_components.ha_alarm_clock.data import AlarmState
    from homeassistant.config_entries import ConfigSubentry
    from homeassistant.helpers.entity import EntityDescription


class SunriseAlarmEntity(CoordinatorEntity[SunriseAlarmDataUpdateCoordinator]):
    """
    Base entity for the entities of one alarm.

    Every alarm is a config subentry with its own device, so the subentry ID is both the
    device identifier and the stable half of the unique ID.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SunriseAlarmDataUpdateCoordinator,
        subentry: ConfigSubentry,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._subentry_id = subentry.subentry_id
        self._attr_unique_id = f"{subentry.subentry_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer=MANUFACTURER,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def alarm(self) -> AlarmState | None:
        """
        Return the state of the alarm this entity belongs to.

        Returns:
            The alarm state, or None while the subentry is being removed.

        """
        return self.coordinator.data.get(self._subentry_id)
