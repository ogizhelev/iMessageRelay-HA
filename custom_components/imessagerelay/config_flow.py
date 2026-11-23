from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
import voluptuous as vol

from .const import DOMAIN, DEFAULT_PORT


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_TOKEN): str,
    }
)


async def _validate_connection(hass, host: str, port: int, token: str) -> str | None:
    """Return None on success, or an error key string on failure."""
    session = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(10):
            async with session.get(
                f"https://{host}:{port}/health",
                headers={"Authorization": f"Bearer {token}"},
                ssl=False,
            ) as resp:
                if resp.status == 401:
                    return "invalid_auth"
                if resp.status != 200:
                    return "cannot_connect"
                return None
    except Exception:
        return "cannot_connect"


class iMessageRelayConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._port: int = DEFAULT_PORT
        self._token: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> dict:
        errors: dict[str, str] = {}

        if user_input is not None:
            raw = user_input[CONF_HOST].strip()
            host = raw.removeprefix("https://").removeprefix("http://").rstrip("/")
            port = user_input[CONF_PORT]
            token = user_input[CONF_TOKEN].strip()

            unique_id = f"{host}:{port}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            error = await _validate_connection(self.hass, host, port, token)
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=f"iMessage Relay ({host})",
                    data={CONF_HOST: host, CONF_PORT: port, CONF_TOKEN: token},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> dict:
        self._host = discovery_info.host
        self._port = discovery_info.port or DEFAULT_PORT

        unique_id = f"{self._host}:{self._port}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {"host": self._host}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(self, user_input: dict[str, Any] | None = None) -> dict:
        errors: dict[str, str] = {}

        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            error = await _validate_connection(self.hass, self._host, self._port, token)
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=f"iMessage Relay ({self._host})",
                    data={
                        CONF_HOST: self._host,
                        CONF_PORT: self._port,
                        CONF_TOKEN: token,
                    },
                )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            description_placeholders={"host": self._host, "port": str(self._port)},
            errors=errors,
        )
