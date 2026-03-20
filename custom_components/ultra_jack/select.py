"""Select platform for Ultra Jack — Status and Operating mode."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODE_OPTIONS, MODE_OPTIONS_INV, STATUS_LABELS
from .coordinator import UltraJackCoordinator

STATUS_KEY = "23133185"
MODE_KEY   = "23132161"

STATUS_OPTIONS = {v: k for k, v in STATUS_LABELS.items()}  # {"Normal": "2", "Standby": "1"}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: UltraJackCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        UltraJackStatusSelect(coordinator),
        UltraJackModeSelect(coordinator),
    ])


def _device_info(coordinator: UltraJackCoordinator) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.device_address)},
        name=coordinator.device_name,
        manufacturer="Jackery",
        model="Explorer 2000 Ultra (HL Series)",
        serial_number=coordinator.device_sn,
    )


class UltraJackStatusSelect(CoordinatorEntity[UltraJackCoordinator], SelectEntity):
    _attr_has_entity_name = True
    _attr_name    = "Status"
    _attr_options = list(STATUS_OPTIONS.keys())  # ["Normal", "Standby"]

    def __init__(self, coordinator: UltraJackCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id   = f"{coordinator.device_address}_status_select"
        self._attr_device_info = _device_info(coordinator)

    @property
    def current_option(self) -> str | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("status")

    async def async_select_option(self, option: str) -> None:
        value = STATUS_OPTIONS.get(option)
        if value:
            await self.coordinator.async_send_command(STATUS_KEY, value)


class UltraJackModeSelect(CoordinatorEntity[UltraJackCoordinator], SelectEntity):
    _attr_has_entity_name = True
    _attr_name    = "Operating mode"
    _attr_options = list(MODE_OPTIONS.keys())

    def __init__(self, coordinator: UltraJackCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id   = f"{coordinator.device_address}_mode_select"
        self._attr_device_info = _device_info(coordinator)

    @property
    def current_option(self) -> str | None:
        if self.coordinator.data is None:
            return None
        return MODE_OPTIONS_INV.get(self.coordinator.data.get("mode_raw", ""))

    async def async_select_option(self, option: str) -> None:
        value = MODE_OPTIONS.get(option)
        if value:
            await self.coordinator.async_send_command(MODE_KEY, value)
