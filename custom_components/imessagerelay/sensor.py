from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import iMessageRelayCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: iMessageRelayCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            QueueDepthSensor(coordinator, entry),
            RunnerStateSensor(coordinator, entry),
        ]
    )


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Homelab",
        model="iMessage Relay",
        configuration_url=f"https://{entry.data['host']}:{entry.data['port']}/health",
    )


class QueueDepthSensor(CoordinatorEntity[iMessageRelayCoordinator], SensorEntity):
    _attr_icon = "mdi:tray-full"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "jobs"
    _attr_has_entity_name = True
    _attr_name = "Queue Depth"

    def __init__(self, coordinator: iMessageRelayCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_queue_depth"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("queueDepth")

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        return {"uptime": data.get("uptime"), "last_callback_at": data.get("lastCallbackAt")}


class RunnerStateSensor(CoordinatorEntity[iMessageRelayCoordinator], SensorEntity):
    _attr_icon = "mdi:state-machine"
    _attr_has_entity_name = True
    _attr_name = "Runner State"

    def __init__(self, coordinator: iMessageRelayCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_runner_state"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.get("runnerState")

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        aliases = data.get("aliases", {})
        return {"aliases": list(aliases.keys()), "alias_count": len(aliases)}
