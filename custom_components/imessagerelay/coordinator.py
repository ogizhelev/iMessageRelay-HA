from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta

import async_timeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL


class iMessageRelayCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, host: str, port: int, token: str) -> None:
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.host = host
        self.port = port
        self.token = token
        self._base_url = f"https://{host}:{port}"

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def _async_update_data(self) -> dict:
        session = async_get_clientsession(self.hass)
        try:
            async with async_timeout.timeout(10):
                async with session.get(
                    f"{self._base_url}/health", headers=self._headers, ssl=False
                ) as resp:
                    resp.raise_for_status()
                    health: dict = await resp.json()

                async with session.get(
                    f"{self._base_url}/aliases", headers=self._headers, ssl=False
                ) as resp:
                    resp.raise_for_status()
                    aliases: dict = await resp.json()

            return {**health, "aliases": aliases}
        except asyncio.TimeoutError as exc:
            raise UpdateFailed("Timeout connecting to iMessage Relay") from exc
        except Exception as exc:
            raise UpdateFailed(f"Error communicating with iMessage Relay: {exc}") from exc

    async def async_send_message(
        self, to: str, text: str, attach: dict | None = None
    ) -> dict:
        payload: dict = {"to": to, "text": text}
        if attach:
            payload["attach"] = attach

        session = async_get_clientsession(self.hass)
        async with async_timeout.timeout(60):
            async with session.post(
                f"{self._base_url}/send",
                headers={**self._headers, "Idempotency-Key": str(uuid.uuid4()), "Content-Type": "application/json"},
                json=payload,
                ssl=False,
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def async_add_alias(self, name: str, contact: str) -> None:
        session = async_get_clientsession(self.hass)
        async with async_timeout.timeout(10):
            async with session.post(
                f"{self._base_url}/alias",
                headers={**self._headers, "Content-Type": "application/json"},
                json={"name": name, "contact": contact},
                ssl=False,
            ) as resp:
                resp.raise_for_status()

    async def async_remove_alias(self, name: str) -> None:
        session = async_get_clientsession(self.hass)
        async with async_timeout.timeout(10):
            async with session.delete(
                f"{self._base_url}/alias/{name}",
                headers=self._headers,
                ssl=False,
            ) as resp:
                resp.raise_for_status()
