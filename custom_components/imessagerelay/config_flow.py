from __future__ import annotations

import asyncio
import logging
import ssl
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
import voluptuous as vol

from .const import DOMAIN, DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)


def _build_ssl(verify: bool) -> bool | ssl.SSLContext:
    if verify:
        return True
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_TOKEN): str,
        vol.Optional(CONF_VERIFY_SSL, default=False): bool,
    }
)


async def _validate_connection(
    hass, host: str, port: int, token: str, verify_ssl: bool = False
) -> str | None:
    """Return None on success, or an error key string on failure."""
    ssl_param = _build_ssl(verify_ssl)
    session = async_get_clientsession(hass, verify_ssl=verify_ssl)
    try:
        async with asyncio.timeout(10):
            async with session.get(
                f"https://{host}:{port}/health",
                headers={"Authorization": f"Bearer {token}"},
                ssl=ssl_param,
            ) as resp:
                if resp.status == 401:
                    return "invalid_auth"
                if resp.status != 200:
                    return "cannot_connect"
                return None
    except Exception as exc:
        _LOGGER.warning("iMessageRelay connection check failed: %s", exc)
        return "cannot_connect"


class iMessageRelayConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._port: int = DEFAULT_PORT
        self._token: str | None = None
        self._verify_ssl: bool = False

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> dict:
        errors: dict[str, str] = {}

        if user_input is not None:
            raw = user_input[CONF_HOST].strip()
            host = raw.removeprefix("https://").removeprefix("http://").rstrip("/")
            port = user_input[CONF_PORT]
            token = user_input[CONF_TOKEN].strip()
            verify_ssl = user_input.get(CONF_VERIFY_SSL, False)

            unique_id = f"{host}:{port}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            error = await _validate_connection(self.hass, host, port, token, verify_ssl)
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title="iMessage Relay",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_TOKEN: token,
                        CONF_VERIFY_SSL: verify_ssl,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            raw = user_input[CONF_HOST].strip()
            host = raw.removeprefix("https://").removeprefix("http://").rstrip("/")
            port = user_input[CONF_PORT]
            token = user_input[CONF_TOKEN].strip()
            verify_ssl = user_input.get(CONF_VERIFY_SSL, False)

            error = await _validate_connection(self.hass, host, port, token, verify_ssl)
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data={
                        **entry.data,
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_TOKEN: token,
                        CONF_VERIFY_SSL: verify_ssl,
                    },
                )

        current = entry.data
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=current.get(CONF_HOST, "")): str,
                    vol.Required(CONF_PORT, default=current.get(CONF_PORT, DEFAULT_PORT)): int,
                    vol.Required(CONF_TOKEN, default=current.get(CONF_TOKEN, "")): str,
                    vol.Optional(CONF_VERIFY_SSL, default=current.get(CONF_VERIFY_SSL, False)): bool,
                }
            ),
            errors=errors,
        )
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
            verify_ssl = user_input.get(CONF_VERIFY_SSL, False)
            error = await _validate_connection(
                self.hass, self._host, self._port, token, verify_ssl
            )
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title="iMessage Relay",
                    data={
                        CONF_HOST: self._host,
                        CONF_PORT: self._port,
                        CONF_TOKEN: token,
                        CONF_VERIFY_SSL: verify_ssl,
                    },
                )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TOKEN): str,
                    vol.Optional(CONF_VERIFY_SSL, default=False): bool,
                }
            ),
            description_placeholders={"host": self._host, "port": str(self._port)},
            errors=errors,
        )
