from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import discovery

from .const import CONF_ENTRY_ID, DOMAIN
from .coordinator import iMessageRelayCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = iMessageRelayCoordinator(
        hass,
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_TOKEN],
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {CONF_ENTRY_ID: entry.entry_id},
            {},
        )
    )

    async def handle_add_alias(call: ServiceCall) -> None:
        await coordinator.async_add_alias(call.data["name"], call.data["contact"])
        await coordinator.async_refresh()

    async def handle_remove_alias(call: ServiceCall) -> None:
        await coordinator.async_remove_alias(call.data["name"])
        await coordinator.async_refresh()

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
            hass.services.async_remove(DOMAIN, "add_alias")
            hass.services.async_remove(DOMAIN, "remove_alias")
    return unload_ok
