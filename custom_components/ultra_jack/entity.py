"""Base entity for Ultra Jack."""
from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import UltraJackCoordinator


class UltraJackEntity(CoordinatorEntity[UltraJackCoordinator]):
    """Common base: device info, naming and unique id."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: UltraJackCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id   = f"{coordinator.device_address}_{key}"
        self._attr_device_info = coordinator.device_info
