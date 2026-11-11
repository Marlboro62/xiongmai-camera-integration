"""Interrupteurs : détection de mouvement, image miroir, image retournée, cloud XMEye."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import XiongmaiConfigEntry
from .entity import XiongmaiEntity


@dataclass(frozen=True, kw_only=True)
class XmSwitchDescription(SwitchEntityDescription):
    section: str
    path: list[Any]
    hex: bool = False  # valeur « 0x00000001 » au lieu de true / false


SWITCHES = (
    XmSwitchDescription(key="motion_detect", section="Detect.MotionDetect", path=[0, "Enable"]),
    XmSwitchDescription(key="mirror", section="Camera.Param", path=[0, "PictureMirror"], hex=True, entity_category=EntityCategory.CONFIG),
    XmSwitchDescription(key="flip", section="Camera.Param", path=[0, "PictureFlip"], hex=True, entity_category=EntityCategory.CONFIG),
    XmSwitchDescription(key="cloud", section="NetWork.Nat", path=["NatEnable"], entity_category=EntityCategory.CONFIG),
)


async def async_setup_entry(hass: HomeAssistant, entry: XiongmaiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    c = entry.runtime_data
    async_add_entities(XmSwitch(c, d) for d in SWITCHES if XmSwitch(c, d).raw is not None)


class XmSwitch(XiongmaiEntity, SwitchEntity):
    entity_description: XmSwitchDescription

    def __init__(self, coordinator, description: XmSwitchDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def raw(self) -> Any:
        return self.setting(self.entity_description.section, self.entity_description.path)

    @property
    def is_on(self) -> bool | None:
        v = self.raw
        if v is None:
            return None
        return bool(int(str(v), 16)) if self.entity_description.hex else bool(v)

    async def _set(self, on: bool) -> None:
        d = self.entity_description
        old = self.raw
        new: Any = on
        if d.hex:
            width = max(len(str(old)) - 2, 1) if isinstance(old, str) and old.startswith("0x") else 8
            new = "0x" + format(1 if on else 0, "X").zfill(width)
        await self.coordinator.async_set(d.section, d.path, new)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)
