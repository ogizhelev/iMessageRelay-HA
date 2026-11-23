from __future__ import annotations

import logging

from homeassistant.components.notify import BaseNotificationService, ATTR_TARGET, ATTR_DATA
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .const import CONF_ENTRY_ID, DOMAIN
from .coordinator import iMessageRelayCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_get_service(
    hass: HomeAssistant,
    config: dict,
    discovery_info: dict | None = None,
) -> iMessageRelayNotifyService | None:
    if not discovery_info:
        return None
    coordinator: iMessageRelayCoordinator = hass.data[DOMAIN][discovery_info[CONF_ENTRY_ID]]
    return iMessageRelayNotifyService(hass, coordinator)


class iMessageRelayNotifyService(BaseNotificationService):
    def __init__(self, hass: HomeAssistant, coordinator: iMessageRelayCoordinator) -> None:
        self.hass = hass
        self.coordinator = coordinator

    @property
    def name(self) -> str:
        return "iMessage Relay"

    async def async_send_message(self, message: str = "", **kwargs) -> None:
        targets: list[str] = kwargs.get(ATTR_TARGET, [])
        if not targets:
            raise ServiceValidationError(
                "target is required — provide one or more alias names"
            )

        to = ",".join(t.strip() for t in targets)
        data: dict = kwargs.get(ATTR_DATA) or {}

        attach: dict | None = None
        if "attach_name" in data and "attach_data" in data:
            attach = {"name": data["attach_name"], "data": data["attach_data"]}

        try:
            result = await self.coordinator.async_send_message(to, message, attach)
            _LOGGER.debug("iMessage Relay send queued: %s", result)
        except Exception as exc:
            raise ServiceValidationError(f"Failed to send message: {exc}") from exc
