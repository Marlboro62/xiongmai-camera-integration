"""Mode jour / nuit."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import XiongmaiConfigEntry
from .const import DAY_NIGHT
from .entity import XiongmaiEntity

PATH = ("Camera.Param", [0, "DayNightColor"])


async def async_setup_entry(hass: HomeAssistant, entry: XiongmaiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    e = DayNight(entry.runtime_data)
    if e.setting(*PATH) is not None:
        async_add_entities([e])


class DayNight(XiongmaiEntity, SelectEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(DAY_NIGHT.values())

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "day_night")

    @property
    def current_option(self) -> str | None:
        v = self.setting(*PATH)
        try:
            return DAY_NIGHT.get(int(str(v), 16))
        except ValueError:
            return None

    async def async_select_option(self, option: str) -> None:
        code = next(k for k, v in DAY_NIGHT.items() if v == option)
        old = str(self.setting(*PATH) or "0x00000000")
        width = max(len(old) - 2, 1) if old.startswith("0x") else 8
        await self.coordinator.async_set(PATH[0], PATH[1], "0x" + format(code, "X").zfill(width))
