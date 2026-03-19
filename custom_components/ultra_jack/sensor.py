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
    async_add_entities(UltraJackSensor(coordinator, d) for d in SENSORS)


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
