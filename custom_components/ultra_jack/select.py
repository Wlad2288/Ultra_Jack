"""Select platform for Ultra Jack — Operating mode."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, METER_MODE, MODE_OPTIONS, MODE_OPTIONS_INV
from .coordinator import UltraJackCoordinator
from .entity import UltraJackEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: UltraJackCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([UltraJackModeSelect(coordinator)])


class UltraJackModeSelect(UltraJackEntity, SelectEntity):
    _attr_name    = "Operating mode"
    _attr_options = list(MODE_OPTIONS.keys())

    def __init__(self, coordinator: UltraJackCoordinator) -> None:
        super().__init__(coordinator, "mode_select")

    @property
    def current_option(self) -> str | None:
        if self.coordinator.data is None:
            return None
        return MODE_OPTIONS_INV.get(self.coordinator.data.get("mode_raw", ""))

    async def async_select_option(self, option: str) -> None:
        value = MODE_OPTIONS.get(option)
        if value:
            await self.coordinator.async_send_command(str(METER_MODE), value)
