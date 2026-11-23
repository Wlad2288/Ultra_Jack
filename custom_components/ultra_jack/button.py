"""Button platform for Ultra Jack — Awake."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import UltraJackCoordinator
from .entity import UltraJackEntity

AWAKE_KEY   = "23133185"
AWAKE_VALUE = "2"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: UltraJackCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([UltraJackAwakeButton(coordinator)])


class UltraJackAwakeButton(UltraJackEntity, ButtonEntity):
    _attr_name = "Awake"

    def __init__(self, coordinator: UltraJackCoordinator) -> None:
        super().__init__(coordinator, "awake")

    @property
    def available(self) -> bool:
        # Waking must work even when the last poll failed (e.g. deep standby).
        return True

    async def async_press(self) -> None:
        await self.coordinator.async_send_command(AWAKE_KEY, AWAKE_VALUE)
