"""Sensibilité de la détection de mouvement (1 à 6)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import XiongmaiConfigEntry
from .entity import XiongmaiEntity

PATH = ("Detect.MotionDetect", [0, "Level"])


async def async_setup_entry(hass: HomeAssistant, entry: XiongmaiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    e = MotionLevel(entry.runtime_data)
    if e.native_value is not None:
        async_add_entities([e])


class MotionLevel(XiongmaiEntity, NumberEntity):
    _attr_native_min_value = 1
    _attr_native_max_value = 6
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "motion_level")

    @property
    def native_value(self) -> float | None:
        v = self.setting(*PATH)
        return float(v) if isinstance(v, (int, float)) else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set(PATH[0], PATH[1], int(value))
