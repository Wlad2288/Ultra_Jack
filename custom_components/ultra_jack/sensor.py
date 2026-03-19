"""Sensor platform for Ultra Jack Series."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE, UnitOfEnergy, UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import UltraJackCoordinator


@dataclass(frozen=True)
class UltraJackSensorDescription(SensorEntityDescription):
    pass


SENSORS = (
    UltraJackSensorDescription(
        key="soc",
        name="SOC",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    UltraJackSensorDescription(
        key="capacity_wh",
        name="Available Capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    UltraJackSensorDescription(
        key="ac_input_power",
        name="AC Input Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    UltraJackSensorDescription(
        key="ac_output_power",
        name="AC Output Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: UltraJackCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [UltraJackSensor(coordinator, d) for d in SENSORS]
    entities.append(UltraJackEnergySensor(coordinator, "energy_charged",    "Energy Charged",    "charge"))
    entities.append(UltraJackEnergySensor(coordinator, "energy_discharged", "Energy Discharged", "discharge"))
    async_add_entities(entities)


class UltraJackSensor(CoordinatorEntity[UltraJackCoordinator], SensorEntity):
    entity_description: UltraJackSensorDescription
    _attr_has_entity_name = True

    def __init__(self, coordinator: UltraJackCoordinator,
                 description: UltraJackSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_address}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_address)},
            name=coordinator.device_name,
            manufacturer="Jackery",
            model="Explorer 2000 Ultra (HL Series)",
            serial_number=coordinator.device_sn,
        )

    @property
    def native_value(self) -> Any:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.key)


class UltraJackEnergySensor(
    CoordinatorEntity[UltraJackCoordinator],
    SensorEntity,
    RestoreEntity,
):
    """Cumulative energy sensor (charged or discharged) in kWh.

    Tracks the running total by accumulating positive/negative changes
    in available capacity. State is persisted across restarts via RestoreEntity.

    On first update after restore, _last_capacity is seeded from current
    capacity without adding a delta — preventing a false spike on restart.
    """

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(
        self,
        coordinator: UltraJackCoordinator,
        key: str,
        name: str,
        direction: str,  # "charge" or "discharge"
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = name
        self._direction  = direction
        self._attr_unique_id = f"{coordinator.device_address}_{key}"
        self._energy: float = 0.0
        self._last_capacity: float | None = None  # None = not yet seeded
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_address)},
            name=coordinator.device_name,
            manufacturer="Jackery",
            model="Explorer 2000 Ultra (HL Series)",
            serial_number=coordinator.device_sn,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        # Restore accumulated energy from previous run
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                self._energy = float(last_state.state)
            except ValueError:
                self._energy = 0.0

        # Seed _last_capacity from current data if already available,
        # so the first coordinator update doesn't produce a false delta.
        if self.coordinator.data:
            cap = self.coordinator.data.get("capacity_wh")
            if cap is not None:
                self._last_capacity = float(cap)

    @property
    def native_value(self) -> float:
        return round(self._energy, 4)

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data
        if data is not None:
            cap = data.get("capacity_wh")
            if cap is not None:
                cap = float(cap)
                if self._last_capacity is None:
                    # First update — seed without accumulating
                    self._last_capacity = cap
                else:
                    delta_kwh = (cap - self._last_capacity) / 1000.0
                    self._last_capacity = cap

                    if self._direction == "charge" and delta_kwh > 0:
                        self._energy += delta_kwh
                    elif self._direction == "discharge" and delta_kwh < 0:
                        self._energy += abs(delta_kwh)

        self.async_write_ha_state()
