"""Boutons : redémarrer la caméra, la mettre à l'heure de Home Assistant."""
from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import XiongmaiConfigEntry
from .dvrip import DvripError
from .entity import XiongmaiEntity


async def async_setup_entry(hass: HomeAssistant, entry: XiongmaiConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    c = entry.runtime_data
    async_add_entities([Reboot(c), SyncTime(c)])


class Reboot(XiongmaiEntity, ButtonEntity):
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "reboot")

    async def async_press(self) -> None:
        try:
            await self.coordinator.client.reboot()
        except DvripError as err:
            raise HomeAssistantError(f"Redémarrage refusé : {err}") from err


class SyncTime(XiongmaiEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "sync_time")

    async def async_press(self) -> None:
        # heure locale de Home Assistant, heure d'été comprise
        now = dt_util.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            await self.coordinator.client.set_time(now)
        except DvripError as err:
            raise HomeAssistantError(f"Mise à l'heure refusée : {err}") from err
