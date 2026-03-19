"""DataUpdateCoordinator for Jackery HL Series."""

import logging
from datetime import timedelta
from typing import Any, Optional

from bleak import BleakClient
from bleak_retry_connector import establish_connection

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN, CONF_DEVICE_ADDRESS, CONF_DEVICE_NAME, CONF_DEVICE_SN,
    DEFAULT_UPDATE_INTERVAL, ALL_METER_IDS,
    METER_AC_POWER, METER_SOC, METER_CAPACITY_WH,
)
from .ble_client import JackeryHLBleClient

_LOGGER = logging.getLogger(__name__)


def _parse_meters(info: dict) -> dict:
    result = {}
    for dev in info.get("dev_list", []):
        for entry in dev.get("meter_list", []):
            if isinstance(entry, list) and len(entry) >= 2:
                try:
                    result[int(entry[0])] = entry[1]
                except (ValueError, TypeError):
                    pass
    return result


def _f(v, d=0.0):
    try:
        return float(v)
    except (ValueError, TypeError):
        return d


def _build_data(meters: dict) -> dict:
    ac_power = _f(meters.get(METER_AC_POWER, 0))
    soc_raw  = _f(meters.get(METER_SOC, 0))
    cap_wh   = _f(meters.get(METER_CAPACITY_WH, 0))

    return {
        "soc":              round(soc_raw / 10.0, 1),
        "capacity_wh":      round(cap_wh, 0),
        "ac_input_power":   round(abs(ac_power), 1) if ac_power < 0 else 0.0,
        "ac_output_power":  round(ac_power, 1)      if ac_power > 0 else 0.0,
    }


class JackeryHLCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, config_data: dict) -> None:
        super().__init__(
            hass, _LOGGER,
            name=f"Jackery HL {config_data.get(CONF_DEVICE_NAME, 'Unknown')}",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        self._address     = config_data[CONF_DEVICE_ADDRESS]
        self._device_name = config_data.get(CONF_DEVICE_NAME, "Jackery")
        self._device_sn   = config_data.get(CONF_DEVICE_SN, "")
        self._client: Optional[JackeryHLBleClient] = None

    @property
    def device_name(self) -> str:
        return self._device_name

    @property
    def device_address(self) -> str:
        return self._address

    @property
    def device_sn(self) -> str:
        return self._device_sn

    async def _ensure_connected(self) -> bool:
        if self._client and self._client.is_connected:
            return True
        _LOGGER.debug("Connecting to %s (%s)", self._device_name, self._address)
        ble_device = async_ble_device_from_address(
            self.hass, self._address, connectable=True
        )
        if not ble_device:
            raise UpdateFailed(f"Device {self._device_name} not found via HA Bluetooth")
        self._client = JackeryHLBleClient(self._device_sn)
        bleak_client = await establish_connection(
            BleakClient, ble_device, self._device_name
        )
        success = await self._client.connect_with_client(bleak_client)
        if not success:
            self._client = None
            raise UpdateFailed(f"Failed to connect to {self._device_name}")
        return True

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            await self._ensure_connected()
        except Exception as err:
            raise UpdateFailed(f"Connection error: {err}") from err

        response = await self._client.query_data(ALL_METER_IDS, timeout=12.0)

        if response is None:
            # Don't disconnect on timeout — keep connection alive, just skip this poll
            _LOGGER.debug("No response this poll cycle, keeping connection for next try")
            if self.data:
                # Return last known good data so sensors stay available
                return self.data
            raise UpdateFailed("No response from device")

        info   = response.get("info", {})
        meters = _parse_meters(info)

        if not meters:
            _LOGGER.warning("Empty meter data, keeping last values")
            if self.data:
                return self.data
            raise UpdateFailed("No meter readings in response")

        data = _build_data(meters)
        _LOGGER.debug("Sensor data: %s", data)
        return data

    async def async_shutdown(self) -> None:
        if self._client:
            await self._client.disconnect()
            self._client = None
