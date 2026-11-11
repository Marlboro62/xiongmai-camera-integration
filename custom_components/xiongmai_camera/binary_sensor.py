"""Mouvement (alarmes poussées par la caméra) et connexion."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import XiongmaiConfigEntry
from .entity import XiongmaiEntity


async def async_setup_entry(hass: HomeAssistant, entry: XiongmaiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    c = entry.runtime_data
    async_add_entities([Motion(c), Online(c)])


class Motion(XiongmaiEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.MOTION

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "motion")

    @property
    def is_on(self) -> bool:
        return self.coordinator.motion


class Online(XiongmaiEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "online")

    @property
    def available(self) -> bool:
        return True  # reste disponible pour dire « Déconnecté »

    @property
    def is_on(self) -> bool:
        return self.coordinator.last_update_success
