"""Diagnostics : sans mot de passe, adresse, numéro de série ni adresse MAC."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import XiongmaiConfigEntry

TO_REDACT = {CONF_PASSWORD, CONF_HOST, "unique_id", "SerialNo", "MAC", "title"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: XiongmaiConfigEntry) -> dict[str, Any]:
    c = entry.runtime_data
    data = c.data or {}
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "last_update_success": c.last_update_success,
        "alarm_events_received": c.events_connected,
        "info": async_redact_data(data.get("info") or {}, TO_REDACT),
        "sections": {k: (v is not None) for k, v in data.items() if k != "info"},
    }
