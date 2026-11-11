"""Temps de fonctionnement de la caméra."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import XiongmaiConfigEntry
from .entity import XiongmaiEntity


async def async_setup_entry(hass: HomeAssistant, entry: XiongmaiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    async_add_entities([Uptime(entry.runtime_data)])


class Uptime(XiongmaiEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_unit_of_measurement = UnitOfTime.DAYS

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "uptime")

    @property
    def native_value(self) -> int | None:
        v = ((self.coordinator.data or {}).get("info") or {}).get("DeviceRunTime")
        try:
            return int(str(v), 16) if str(v).startswith("0x") else int(v)
        except (TypeError, ValueError):
            return None
