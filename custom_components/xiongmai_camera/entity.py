"""Entité de base : un appareil par caméra."""
from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import XiongmaiCoordinator


class XiongmaiEntity(CoordinatorEntity[XiongmaiCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: XiongmaiCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}_{key}"
        self._attr_translation_key = key
        info = (coordinator.data or {}).get("info") or {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            name=entry.data.get(CONF_NAME) or entry.title,
            manufacturer="XiongMai",
            model=info.get("HardWare") or None,
            sw_version=info.get("SoftWareVersion") or None,
            configuration_url=f"http://{entry.data[CONF_HOST]}/",
        )

    def value(self, section: str, path: list[Any]) -> Any:
        """Valeur d'un réglage, ou None s'il n'existe pas sur ce modèle."""
        v: Any = (self.coordinator.data or {}).get(section)
        try:
            for key in path:
                v = v[key]
        except (KeyError, IndexError, TypeError):
            return None
        return v
