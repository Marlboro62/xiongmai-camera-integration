"""Paramétrage : adresse, port, identifiants de la caméra ; reconfiguration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.helpers import selector

from .const import DEFAULT_PORT, DEFAULT_USERNAME, DOMAIN
from .dvrip import DvripClient, DvripError

LOGIN_ERRORS = {106, 203, 204, 205, 206}


def _schema(d: dict[str, Any]) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_NAME, default=d.get(CONF_NAME, "Caméra")): str,
        vol.Required(CONF_HOST, default=d.get(CONF_HOST, "")): str,
        vol.Required(CONF_PORT, default=d.get(CONF_PORT, DEFAULT_PORT)): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
        vol.Required(CONF_USERNAME, default=d.get(CONF_USERNAME, DEFAULT_USERNAME)): str,
        vol.Optional(CONF_PASSWORD, default=d.get(CONF_PASSWORD, "")): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
    })


async def _check(d: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Connexion d'essai : (infos système, erreur)."""
    client = DvripClient(d[CONF_HOST].strip(), d[CONF_PORT], d[CONF_USERNAME], d.get(CONF_PASSWORD) or "")
    try:
        return await client.system_info(), None
    except DvripError as err:
        return None, "invalid_auth" if err.ret in LOGIN_ERRORS else "cannot_connect"
    finally:
        await client.close()


class XiongmaiConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_HOST] = user_input[CONF_HOST].strip()
            info, error = await _check(user_input)
            if error:
                errors["base"] = error
            else:
                # identifiant stable : numéro de série (jamais affiché), sinon l'adresse
                await self.async_set_unique_id(str(info.get("SerialNo") or user_input[CONF_HOST]))
                self._abort_if_unique_id_configured(updates={CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]})
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
        return self.async_show_form(step_id="user", data_schema=_schema(user_input or {}), errors=errors)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_HOST] = user_input[CONF_HOST].strip()
            _info, error = await _check(user_input)
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(step_id="reconfigure", data_schema=_schema(user_input or dict(entry.data)), errors=errors)
