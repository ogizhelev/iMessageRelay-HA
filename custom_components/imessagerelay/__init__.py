from __future__ import annotations

import logging

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN
from .coordinator import iMessageRelayCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = iMessageRelayCoordinator(
        hass,
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_TOKEN],
        entry.data.get(CONF_VERIFY_SSL, False),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def handle_send_message(call: ServiceCall) -> None:
        targets: list[str] = call.data["target"]
        to = ",".join(t.strip() for t in targets)
        message: str = call.data["message"]
        data: dict = call.data.get("data") or {}

        attach: dict | None = None
        if "attach_name" in data and "attach_data" in data:
            attach = {"name": data["attach_name"], "data": data["attach_data"]}

        result = await coordinator.async_send_message(to, message, attach)
        _LOGGER.debug("iMessage Relay send queued: %s", result)

    async def handle_add_alias(call: ServiceCall) -> None:
        await coordinator.async_add_alias(call.data["name"], call.data["contact"])
        await coordinator.async_refresh()

    async def handle_remove_alias(call: ServiceCall) -> None:
        await coordinator.async_remove_alias(call.data["name"])
        await coordinator.async_refresh()

    if not hass.services.has_service(DOMAIN, "send_message"):
        hass.services.async_register(
            DOMAIN,
            "send_message",
            handle_send_message,
            schema=vol.Schema(
                {
                    vol.Required("message"): str,
                    vol.Required("target"): vol.All(cv.ensure_list, [str]),
                    vol.Optional("data"): dict,
                }
            ),
        )

    if not hass.services.has_service(DOMAIN, "add_alias"):
        hass.services.async_register(
            DOMAIN,
            "add_alias",
            handle_add_alias,
            schema=vol.Schema(
                {vol.Required("name"): str, vol.Required("contact"): str}
            ),
        )

    if not hass.services.has_service(DOMAIN, "remove_alias"):
        hass.services.async_register(
            DOMAIN,
            "remove_alias",
            handle_remove_alias,
            schema=vol.Schema({vol.Required("name"): str}),
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "send_message")
            hass.services.async_remove(DOMAIN, "add_alias")
            hass.services.async_remove(DOMAIN, "remove_alias")
    return unload_ok
