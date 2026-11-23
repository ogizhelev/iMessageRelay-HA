from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import iMessageRelayCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: iMessageRelayCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([iMessageRelayNotifyEntity(coordinator, entry)])


class iMessageRelayNotifyEntity(CoordinatorEntity[iMessageRelayCoordinator], NotifyEntity):
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: iMessageRelayCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_notify"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Homelab",
            model="iMessage Relay",
            configuration_url=f"https://{entry.data['host']}:{entry.data['port']}/health",
        )

    async def async_send_message(self, message: str, title: str | None = None, **kwargs: Any) -> None:
        targets: list[str] = kwargs.get("target", [])
        if not targets:
            raise ServiceValidationError(
                "target is required — provide one or more alias names"
            )
        to = ",".join(str(t).strip() for t in targets)
        data: dict = kwargs.get("data") or {}

        attach: dict | None = None
        if "attach_name" in data and "attach_data" in data:
            attach = {"name": data["attach_name"], "data": data["attach_data"]}

        try:
            result = await self.coordinator.async_send_message(to, message, attach)
            _LOGGER.debug("iMessage Relay send queued: %s", result)
        except Exception as exc:
            raise ServiceValidationError(f"Failed to send message: {exc}") from exc
