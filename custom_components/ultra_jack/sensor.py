"""Sensor platform for Ultra Jack Series."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import logging
import time

from homeassistant.components.sensor import (
    SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import UltraJackCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class UltraJackSensorDescription(SensorEntityDescription):
    pass


SENSORS = (
    UltraJackSensorDescription(
        key="status",
        name="Status",
        device_class=None,
        state_class=None,
    ),
    UltraJackSensorDescription(
        key="mode",
        name="Operating mode",
        device_class=None,
        state_class=None,
    ),
    UltraJackSensorDescription(
        key="soc",
        name="SOC",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    UltraJackSensorDescription(
        key="capacity_wh",
        name="Available capacity",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    UltraJackSensorDescription(
        key="ac_input_power",
        name="AC input power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    UltraJackSensorDescription(
        key="ac_output_power",
        name="AC output power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    UltraJackSensorDescription(
        key="dc_input_power",
        name="DC input power",
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
    entities.append(UltraJackPowerIntegrationSensor(coordinator, "energy_charged",    "Energy charged",    "charge"))
    entities.append(UltraJackPowerIntegrationSensor(coordinator, "energy_discharged", "Energy discharged", "discharge"))
    entities.append(UltraJackPowerIntegrationSensor(coordinator, "energy_loss",       "Energy loss",       "loss"))
    entities.append(UltraJackPowerIntegrationSensor(coordinator, "solar_energy",      "Solar energy",      "solar"))
    async_add_entities(entities)


def _device_info(coordinator: UltraJackCoordinator) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.device_address)},
        name=coordinator.device_name,
        manufacturer="Jackery",
        model="Explorer 2000 Ultra (HL Series)",
        serial_number=coordinator.device_sn,
    )


class UltraJackSensor(CoordinatorEntity[UltraJackCoordinator], SensorEntity):
    entity_description: UltraJackSensorDescription
    _attr_has_entity_name = True

    def __init__(self, coordinator: UltraJackCoordinator,
                 description: UltraJackSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description    = description
        self._attr_unique_id       = f"{coordinator.device_address}_{description.key}"
        self._attr_device_info     = _device_info(coordinator)

    @property
    def native_value(self) -> Any:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.key)


class UltraJackPowerIntegrationSensor(
    CoordinatorEntity[UltraJackCoordinator],
    SensorEntity,
    RestoreEntity,
):
    """Cumulative energy sensor (kWh) based on power integration over time.

    direction:
      charge    — integrates AC input power + DC input power
      discharge — integrates AC output power (> 10W threshold)
      loss      — integrates based on capacity drop with no AC output (standby/self-discharge)

    Using power integration (W × time) instead of capacity deltas gives:
    - More accurate results (no quantization from 1Wh capacity steps)
    - Correct DC charging attribution
    - Proper Energy Dashboard support
    """

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class  = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator: UltraJackCoordinator,
                 key: str, name: str, direction: str) -> None:
        super().__init__(coordinator)
        self._attr_name       = name
        self._direction       = direction
        self._attr_unique_id  = f"{coordinator.device_address}_{key}"
        self._attr_device_info = _device_info(coordinator)
        self._energy: float = 0.0
        self._last_ts: float | None = None
        # For loss direction: still use capacity delta method
        self._last_capacity: float | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                self._energy = float(last_state.state)
            except ValueError:
                self._energy = 0.0
        # Seed timestamp and capacity
        self._last_ts = time.monotonic()
        if self.coordinator.data:
            cap = self.coordinator.data.get("capacity_wh")
            if cap is not None:
                self._last_capacity = float(cap)

    @property
    def native_value(self) -> float:
        return round(self._energy, 4)

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data
        now = time.monotonic()

        if data is not None and self._last_ts is not None:
            elapsed_h = (now - self._last_ts) / 3600.0

            # Sanity check: ignore if elapsed time is too large (> 5 minutes)
            # This prevents false accumulation after long offline periods
            if elapsed_h <= 5 / 60:

                ac_in  = float(data.get("ac_input_power")  or 0)
                dc_in  = float(data.get("dc_input_power")  or 0)
                ac_out = float(data.get("ac_output_power") or 0)

                if self._direction == "charge":
                    # Total charging power: AC input + DC input
                    total_charge_w = ac_in + dc_in
                    if total_charge_w > 0:
                        self._energy += (total_charge_w * elapsed_h) / 1000.0

                elif self._direction == "solar":
                    # DC/PV input only — for Energy Dashboard solar production
                    if dc_in > 0:
                        self._energy += (dc_in * elapsed_h) / 1000.0

                elif self._direction == "discharge":
                    # Only real load on AC output
                    if ac_out > 10:
                        self._energy += (ac_out * elapsed_h) / 1000.0

                elif self._direction == "loss":
                    # Standby losses: capacity drops with no AC output
                    # Keep capacity delta method for losses (more accurate for slow drain)
                    cap = data.get("capacity_wh")
                    if cap is not None:
                        cap = float(cap)
                        if self._last_capacity is not None:
                            delta_wh = cap - self._last_capacity
                            if -200 < delta_wh < 0 and ac_out <= 10:
                                self._energy += abs(delta_wh) / 1000.0
                        self._last_capacity = cap

        self._last_ts = now
        self.async_write_ha_state()
