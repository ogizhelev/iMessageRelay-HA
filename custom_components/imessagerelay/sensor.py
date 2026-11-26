from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_WEBHOOK_ID, DOMAIN
from .coordinator import iMessageRelayCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: iMessageRelayCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ConnectionSensor(coordinator, entry),
            QueueDepthSensor(coordinator, entry),
            RunnerStateSensor(coordinator, entry),
            AliasesSensor(coordinator, entry),
            BatterySensor(coordinator, entry),
            WebhookSensor(hass, entry),
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


class ConnectionSensor(CoordinatorEntity[iMessageRelayCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Connection"

    def __init__(self, coordinator: iMessageRelayCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_connection"
        self._attr_device_info = _device_info(entry)

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> str:
        return "connected" if self.coordinator.last_update_success else "disconnected"

    @property
    def icon(self) -> str:
        return "mdi:lan-connect" if self.coordinator.last_update_success else "mdi:lan-disconnect"

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {
            "host": self.coordinator.host,
            "port": self.coordinator.port,
            "response_time_ms": self.coordinator.response_time_ms,
        }
        if self.coordinator.last_seen:
            attrs["last_seen"] = self.coordinator.last_seen.isoformat()
        return attrs


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
        return (self.coordinator.data or {}).get("queueDepth")

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
        return (self.coordinator.data or {}).get("runnerState")


class AliasesSensor(CoordinatorEntity[iMessageRelayCoordinator], SensorEntity):
    _attr_icon = "mdi:account-multiple"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "aliases"
    _attr_has_entity_name = True
    _attr_name = "Aliases"

    def __init__(self, coordinator: iMessageRelayCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_aliases"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> int:
        return len((self.coordinator.data or {}).get("aliases", {}))

    @property
    def extra_state_attributes(self) -> dict:
        return (self.coordinator.data or {}).get("aliases", {})


class BatterySensor(CoordinatorEntity[iMessageRelayCoordinator], SensorEntity):
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_has_entity_name = True
    _attr_name = "Battery"

    def __init__(self, coordinator: iMessageRelayCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_battery"
        self._attr_device_info = _device_info(entry)

    def _battery(self) -> dict:
        return (self.coordinator.data or {}).get("battery") or {}

    @property
    def native_value(self) -> int | None:
        percentage = self._battery().get("percentage")
        if not isinstance(percentage, int) or percentage < 0:
            return None
        return percentage

    @property
    def icon(self) -> str:
        battery = self._battery()
        if battery.get("charging"):
            return "mdi:battery-charging"
        percentage = battery.get("percentage")
        if not isinstance(percentage, int) or percentage < 0:
            return "mdi:battery-unknown"
        if percentage >= 95:
            return "mdi:battery"
        if percentage <= 5:
            return "mdi:battery-alert"
        return f"mdi:battery-{round(percentage / 10) * 10}"

    @property
    def extra_state_attributes(self) -> dict:
        battery = self._battery()
        return {
            "connected": battery.get("connected"),
            "charging": battery.get("charging"),
            "state": battery.get("state"),
            "low_power_mode": battery.get("low_power_mode"),
        }


class WebhookSensor(SensorEntity):
    _attr_icon = "mdi:webhook"
    _attr_has_entity_name = True
    _attr_name = "Webhook"
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_webhook"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str:
        return "active" if self._entry.data.get(CONF_WEBHOOK_ID) else "not configured"

    @property
    def extra_state_attributes(self) -> dict:
        webhook_id = self._entry.data.get(CONF_WEBHOOK_ID, "")
        if not webhook_id:
            return {}
        path = f"/api/webhook/{webhook_id}"
        try:
            base = get_url(self.hass)
            return {"url": f"{base}{path}", "path": path}
        except NoURLAvailableError:
            return {"path": path}

