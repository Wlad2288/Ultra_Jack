"""Button platform for Ultra Jack — Status control."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import UltraJackCoordinator

STATUS_KEY = "23133185"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: UltraJackCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        UltraJackButton(coordinator, "status_normal",  "Status Normal",  STATUS_KEY, "2"),
        UltraJackButton(coordinator, "status_standby", "Status Standby", STATUS_KEY, "1"),
    ])


class UltraJackButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: UltraJackCoordinator,
                 key: str, name: str, cmd_key: str, cmd_value: str) -> None:
        self._coordinator  = coordinator
        self._cmd_key      = cmd_key
        self._cmd_value    = cmd_value
        self._attr_name       = name
        self._attr_unique_id  = f"{coordinator.device_address}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_address)},
            name=coordinator.device_name,
            manufacturer="Jackery",
            model="Explorer 2000 Ultra (HL Series)",
            serial_number=coordinator.device_sn,
        )

    async def async_press(self) -> None:
        await self._coordinator.async_send_command(self._cmd_key, self._cmd_value)
