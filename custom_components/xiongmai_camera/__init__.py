"""Caméra XiongMai : entités Home Assistant pour les caméras XiongMai / XMEye / NetSurveillance (protocole DVRIP)."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import MOTION_TIMEOUT
from .coordinator import XiongmaiCoordinator
from .dvrip import DvripClient, DvripEvents

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.NUMBER, Platform.SELECT, Platform.SENSOR, Platform.SWITCH]

type XiongmaiConfigEntry = ConfigEntry[XiongmaiCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: XiongmaiConfigEntry) -> bool:
    d = entry.data
    client = DvripClient(d[CONF_HOST], d[CONF_PORT], d[CONF_USERNAME], d.get(CONF_PASSWORD, ""))
    coordinator = XiongmaiCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # alarmes poussées par la caméra (mouvement) sur une seconde connexion
    timer: dict[str, CALLBACK_TYPE | None] = {"cancel": None}

    @callback
    def _reset_motion(_now) -> None:
        timer["cancel"] = None
        if coordinator.motion:
            coordinator.motion = False
            coordinator.async_update_listeners()

    @callback
    def _on_alarm(event: str, channel: int, active: bool) -> None:
        if event != "VideoMotion" or channel != 0:
            return
        coordinator.events_connected = True
        if timer["cancel"]:
            timer["cancel"]()
            timer["cancel"] = None
        if active:  # filet de sécurité si la fin de l'événement n'arrive pas
            timer["cancel"] = async_call_later(hass, MOTION_TIMEOUT, _reset_motion)
        if coordinator.motion != active:
            coordinator.motion = active
            coordinator.async_update_listeners()

    events = DvripEvents(d[CONF_HOST], d[CONF_PORT], d[CONF_USERNAME], d.get(CONF_PASSWORD, ""), _on_alarm)
    task = entry.async_create_background_task(hass, events.run(), f"xiongmai_camera alarmes {d[CONF_HOST]}")

    async def _close() -> None:
        if timer["cancel"]:
            timer["cancel"]()
        task.cancel()
        await events.close()
        await client.close()

    entry.async_on_unload(_close)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: XiongmaiConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
