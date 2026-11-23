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
from homeassistant.const import (
    PERCENTAGE, STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfEnergy, UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import UltraJackCoordinator
from .entity import UltraJackEntity

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


class UltraJackSensor(UltraJackEntity, SensorEntity):
    entity_description: UltraJackSensorDescription

    def __init__(self, coordinator: UltraJackCoordinator,
                 description: UltraJackSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.key)


class UltraJackPowerIntegrationSensor(UltraJackEntity, SensorEntity, RestoreEntity):
    """Cumulative energy sensor (kWh) based on power integration over time.

    direction:
      charge    — integrates AC input power + DC input power
      solar     — integrates DC/PV input power
      discharge — integrates AC output power (> 10W threshold)
      loss      — integrates based on capacity drop with no AC output (standby/self-discharge)

    Using power integration (W × time) instead of capacity deltas gives:
    - More accurate results (no quantization from 1Wh capacity steps)
    - Correct DC charging attribution
    - Proper Energy Dashboard support
    """

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class  = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator: UltraJackCoordinator,
                 key: str, name: str, direction: str) -> None:
        super().__init__(coordinator, key)
        self._attr_name  = name
        self._direction  = direction
        self._energy: float = 0.0
        self._last_ts: float | None = None
        # updated_at of the last reading that was integrated. Prevents
        # re-integrating cached data while the device is unreachable.
        self._last_reading: float | None = None
        # For loss direction: still use capacity delta method
        self._last_capacity: float | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                self._energy = float(last_state.state)
            except ValueError:
                self._energy = 0.0
        # Seed timestamp and capacity
        self._last_ts = time.monotonic()
        if self.coordinator.data:
            self._last_reading = self.coordinator.data.get("updated_at")
            cap = self.coordinator.data.get("capacity_wh")
            if cap is not None:
                self._last_capacity = float(cap)

    @property
    def native_value(self) -> float:
        return round(self._energy, 4)

    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data
        if data is None or data.get("updated_at") == self._last_reading:
            # No new reading (poll failed and cached values were kept):
            # don't integrate the same power value again, but still publish
            # availability changes.
            self.async_write_ha_state()
            return
        self._last_reading = data.get("updated_at")
        now = time.monotonic()

        if self._last_ts is not None:
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

            elif data.get("capacity_wh") is not None:
                # Long gap: re-seed so the next delta isn't counted as loss.
                self._last_capacity = float(data["capacity_wh"])

        self._last_ts = now
        self.async_write_ha_state()
