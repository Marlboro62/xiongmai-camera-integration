"""Lecture périodique de la caméra (protocole DVRIP) et écriture des réglages."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL, SECTIONS
from .dvrip import DvripClient, DvripError

_LOGGER = logging.getLogger(__name__)


class XiongmaiCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Données : infos système, heure de la caméra, sections du firmware."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: DvripClient) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.client = client
        self.motion = False  # alimenté par les alarmes poussées par la caméra
        self.events_connected = False

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            info = await self.client.system_info()
        except DvripError as err:
            raise UpdateFailed(f"Caméra injoignable : {err}") from err
        data: dict[str, Any] = {"info": info}
        for name in SECTIONS:
            try:
                data[name] = await self.client.get_config(name)
            except DvripError:
                data[name] = None  # réglage absent sur ce modèle
        return data

    async def async_set(self, section: str, path: list[Any], value: Any) -> None:
        """Change une valeur : relit la section, la modifie, l'écrit, puis rafraîchit."""
        try:
            conf = await self.client.get_config(section)
            target = conf
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            await self.client.set_config(section, conf)
        except (DvripError, KeyError, IndexError, TypeError) as err:
            raise HomeAssistantError(f"Réglage refusé par la caméra : {err}") from err
        await self.async_request_refresh()
