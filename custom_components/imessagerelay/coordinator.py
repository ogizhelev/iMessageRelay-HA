from __future__ import annotations

import asyncio
import logging
import ssl
import uuid
from datetime import datetime, timedelta, timezone
from time import monotonic

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL


class iMessageRelayCoordinator(DataUpdateCoordinator):
    def __init__(
        self, hass: HomeAssistant, host: str, port: int, token: str, verify_ssl: bool = False
    ) -> None:
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.host = host
        self.port = port
        self.token = token
        self._base_url = f"https://{host}:{port}"
        self._verify_ssl = verify_ssl
        if verify_ssl:
            self._ssl: bool | ssl.SSLContext = True
        else:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            self._ssl = ctx

        self.response_time_ms: int | None = None
        self.last_seen: datetime | None = None

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def _async_update_data(self) -> dict:
        session = async_get_clientsession(self.hass, verify_ssl=self._verify_ssl)
        try:
            async with asyncio.timeout(10):
                t0 = monotonic()
                async with session.get(
                    f"{self._base_url}/health", headers=self._headers, ssl=self._ssl
                ) as resp:
                    resp.raise_for_status()
                    health: dict = await resp.json()
                self.response_time_ms = round((monotonic() - t0) * 1000)
                self.last_seen = datetime.now(timezone.utc)

                async with session.get(
                    f"{self._base_url}/aliases", headers=self._headers, ssl=self._ssl
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

        session = async_get_clientsession(self.hass, verify_ssl=self._verify_ssl)
        async with asyncio.timeout(60):
            async with session.post(
                f"{self._base_url}/send",
                headers={**self._headers, "Idempotency-Key": str(uuid.uuid4()), "Content-Type": "application/json"},
                json=payload,
                ssl=self._ssl,
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def async_add_alias(self, name: str, contact: str) -> None:
        session = async_get_clientsession(self.hass, verify_ssl=self._verify_ssl)
        async with asyncio.timeout(10):
            async with session.post(
                f"{self._base_url}/alias",
                headers={**self._headers, "Content-Type": "application/json"},
                json={"name": name, "contact": contact},
                ssl=self._ssl,
            ) as resp:
                resp.raise_for_status()

    async def async_remove_alias(self, name: str) -> None:
        session = async_get_clientsession(self.hass, verify_ssl=self._verify_ssl)
        async with asyncio.timeout(10):
            async with session.delete(
                f"{self._base_url}/alias/{name}",
                headers=self._headers,
                ssl=self._ssl,
            ) as resp:
                resp.raise_for_status()
