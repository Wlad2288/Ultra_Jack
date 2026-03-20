"""Button platform for Ultra Jack — Awake."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import UltraJackCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: UltraJackCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([UltraJackAwakeButton(coordinator)])


class UltraJackAwakeButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Awake"

    def __init__(self, coordinator: UltraJackCoordinator) -> None:
        self._coordinator = coordinator
        self._attr_unique_id   = f"{coordinator.device_address}_awake"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_address)},
            name=coordinator.device_name,
            manufacturer="Jackery",
            model="Explorer 2000 Ultra (HL Series)",
            serial_number=coordinator.device_sn,
        )

    async def async_press(self) -> None:
        await self._coordinator.async_send_command("23133185", "2")
