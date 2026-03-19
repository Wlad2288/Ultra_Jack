"""Sensor platform for Ultra Jack Series."""
from __future__ import annotations
from dataclasses import dataclass
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
    entities = [UltraJackSensor(coordinator, d) for d in SENSORS]
    entities.append(
        UltraJackEnergySensor(
            coordinator,
            "energy_charged",
            "Energy Charged",
            "charge",
        )
    )
    entities.append(
        UltraJackEnergySensor(
            coordinator,
            "energy_discharged",
            "Energy Discharged",
            "discharge",
        )
    )
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


from datetime import datetime, timezone
from homeassistant.helpers.restore_state import RestoreEntity


class UltraJackEnergySensor(
    CoordinatorEntity[UltraJackCoordinator],
    SensorEntity,
    RestoreEntity,
):
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator, key, name, power_key):
        super().__init__(coordinator)
        self._attr_name = name
        self._power_key = power_key

        self._attr_unique_id = f"{coordinator.device_address}_{key}"

        self._energy = 0.0
        self._last_update: datetime | None = None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_address)},
            name=coordinator.device_name,
            manufacturer="Jackery",
            model="Explorer 2000 Ultra (HL Series)",
            serial_number=coordinator.device_sn,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                self._energy = float(last_state.state)
            except ValueError:
                self._energy = 0.0

    @property
    def native_value(self):
        return round(self._energy, 4)

    def _update_energy(self):
        data = self.coordinator.data
        if data is None:
            return

        capacity_wh = data.get("capacity_wh")
        if capacity_wh is None:
            return

        if not hasattr(self, "_last_capacity"):
            self._last_capacity = capacity_wh
            return

        delta_wh = capacity_wh - self._last_capacity
        self._last_capacity = capacity_wh

        # in kWh umrechnen
        delta_kwh = delta_wh / 1000.0

        if self._power_key == "charge":
            # nur positive Änderungen zählen
            if delta_kwh > 0:
                self._energy += delta_kwh

        elif self._power_key == "discharge":
            # nur negative Änderungen zählen
            if delta_kwh < 0:
                self._energy += abs(delta_kwh)

    def _handle_coordinator_update(self) -> None:
        self._update_energy()
        self.async_write_ha_state()