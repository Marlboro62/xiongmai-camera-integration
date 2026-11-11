"""Paramétrage, entités, commandes, alarmes de mouvement, diagnostics : contre une caméra simulée."""
from __future__ import annotations

import asyncio

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.xiongmai_camera.const import DOMAIN
from custom_components.xiongmai_camera.diagnostics import async_get_config_entry_diagnostics

from . import fake_camera


def _data(port: int, password: str = "demo") -> dict:
    return {"name": "Palier", "host": "127.0.0.1", "port": port, "username": "admin", "password": password}


async def _setup(hass: HomeAssistant, port: int) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title="Palier", data=_data(port), unique_id="0000000000000000")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _eid(hass: HomeAssistant, platform: str, key: str) -> str:
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"0000000000000000_{key}")


async def test_config_flow(hass: HomeAssistant, camera: int) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], _data(camera, "faux"))
    assert result["errors"] == {"base": "invalid_auth"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], _data(camera))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Palier"
    assert result["result"].unique_id == "0000000000000000"
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(result["result"].entry_id)


async def test_cannot_connect(hass: HomeAssistant, socket_enabled) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], _data(1))
    assert result["errors"] == {"base": "cannot_connect"}


async def test_entities_and_commands(hass: HomeAssistant, camera: int) -> None:
    entry = await _setup(hass, camera)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(_eid(hass, "switch", "motion_detect")).state == "on"
    assert hass.states.get(_eid(hass, "switch", "mirror")).state == "off"
    assert hass.states.get(_eid(hass, "select", "day_night")).state == "auto"
    assert hass.states.get(_eid(hass, "number", "motion_level")).state == "3.0"
    assert hass.states.get(_eid(hass, "binary_sensor", "online")).state == "on"
    assert int(hass.states.get(_eid(hass, "sensor", "uptime")).state.split(".")[0]) > 0

    await hass.services.async_call("switch", "turn_on", {"entity_id": _eid(hass, "switch", "mirror")}, blocking=True)
    await hass.async_block_till_done()
    assert fake_camera.CONFIG["Camera.Param"][0]["PictureMirror"] == "0x00000001"
    assert hass.states.get(_eid(hass, "switch", "mirror")).state == "on"

    await hass.services.async_call("select", "select_option", {"entity_id": _eid(hass, "select", "day_night"), "option": "color"}, blocking=True)
    assert fake_camera.CONFIG["Camera.Param"][0]["DayNightColor"] == "0x00000001"

    await hass.services.async_call("number", "set_value", {"entity_id": _eid(hass, "number", "motion_level"), "value": 5}, blocking=True)
    assert fake_camera.CONFIG["Detect.MotionDetect"][0]["Level"] == 5

    await hass.services.async_call("switch", "turn_off", {"entity_id": _eid(hass, "switch", "cloud")}, blocking=True)
    assert fake_camera.CONFIG["NetWork.Nat"]["NatEnable"] is False

    await hass.services.async_call("button", "press", {"entity_id": _eid(hass, "button", "sync_time")}, blocking=True)
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_motion_events(hass: HomeAssistant, camera: int) -> None:
    entry = await _setup(hass, camera)
    motion = _eid(hass, "binary_sensor", "motion")
    assert hass.states.get(motion).state == "off"
    for _ in range(100):  # abonnement aux alarmes
        if fake_camera.SUBSCRIBERS:
            break
        await asyncio.sleep(0.05)
    assert fake_camera.SUBSCRIBERS
    await fake_camera.push_alarm(True)
    for _ in range(100):
        await asyncio.sleep(0.02)
        if hass.states.get(motion).state == "on":
            break
    assert hass.states.get(motion).state == "on"
    await fake_camera.push_alarm(False)
    for _ in range(100):
        await asyncio.sleep(0.02)
        if hass.states.get(motion).state == "off":
            break
    assert hass.states.get(motion).state == "off"
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_diagnostics(hass: HomeAssistant, camera: int) -> None:
    entry = await _setup(hass, camera)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    text = str(diag)
    assert "demo" not in text and "127.0.0.1" not in text and "0000000000000000" not in text
    assert diag["last_update_success"] is True
    assert await hass.config_entries.async_unload(entry.entry_id)
