from __future__ import annotations

import logging
import base64
import os

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.webhook import (
    async_generate_id,
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from .const import CONF_WEBHOOK_ID, DOMAIN, EVENT_MESSAGE_RECEIVED
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

    # Ensure a stable webhook ID is stored in the config entry.
    webhook_id: str = entry.data.get(CONF_WEBHOOK_ID, "")
    if not webhook_id:
        webhook_id = async_generate_id()
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_WEBHOOK_ID: webhook_id}
        )

    async def _handle_webhook(hass: HomeAssistant, _webhook_id: str, request) -> None:
        try:
            body: dict = await request.json()
        except Exception:
            body = {}

        sender = body.get("sender") or body.get("from") or body.get("contact") or ""
        message = body.get("message") or body.get("text") or body.get("body") or ""

        hass.bus.async_fire(
            EVENT_MESSAGE_RECEIVED,
            {
                "sender": sender,
                "message": message,
                "raw": body,
            },
        )
        _LOGGER.debug("iMessageRelay inbound: sender=%r message=%r", sender, message)

    webhook_register(
        hass,
        DOMAIN,
        "iMessage Relay inbound",
        webhook_id,
        _handle_webhook,
        allowed_methods=["POST"],
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def handle_send_message(call: ServiceCall) -> None:
        targets: list[str] = call.data["target"]
        to = ",".join(t.strip() for t in targets)
        message: str = call.data["message"]

        attach: dict | None = None

        if "attach_file_path" in call.data:
            path: str = call.data["attach_file_path"]
            filename = os.path.basename(path)

            def _read_file() -> str:
                with open(path, "rb") as f:
                    return base64.b64encode(f.read()).decode("ascii")

            try:
                encoded = await hass.async_add_executor_job(_read_file)
            except FileNotFoundError:
                raise ServiceValidationError(f"File not found: {path}")
            except PermissionError:
                raise ServiceValidationError(f"Permission denied reading: {path}")
            except Exception as exc:
                raise ServiceValidationError(f"Could not read file: {exc}") from exc

            attach = {"name": filename, "data": encoded}

        elif "attach_name" in call.data and "attach_data" in call.data:
            attach = {"name": call.data["attach_name"], "data": call.data["attach_data"]}

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
                    vol.Optional("attach_file_path"): str,
                    vol.Optional("attach_name"): str,
                    vol.Optional("attach_data"): str,
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
    webhook_id: str = entry.data.get(CONF_WEBHOOK_ID, "")
    if webhook_id:
        webhook_unregister(hass, webhook_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "send_message")
            hass.services.async_remove(DOMAIN, "add_alias")
            hass.services.async_remove(DOMAIN, "remove_alias")
    return unload_ok
