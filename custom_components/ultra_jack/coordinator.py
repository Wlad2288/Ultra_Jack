"""DataUpdateCoordinator for Ultra Jack."""

import json
import logging
import random
import time
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
    METER_STATUS, METER_MODE,
    STATUS_LABELS, MODE_LABELS, MODE_OPTIONS_INV,
    CHAR_WRITE_UUID,
)
from .ble_client import UltraJackBleClient

_LOGGER = logging.getLogger(__name__)


def _parse_meters(info: dict) -> dict:
    result: dict[int, str] = {}
    for dev in info.get("dev_list", []):
        for entry in dev.get("meter_list", []):
            if isinstance(entry, list) and len(entry) >= 2:
                try:
                    result[int(entry[0])] = entry[1]
                except (ValueError, TypeError):
                    pass
    return result


def _f(v: Any, d: float = 0.0) -> float:
    try:
        return float(v)
    except (ValueError, TypeError):
        return d


def _build_sensor_data(meters: dict) -> dict:
    ac_power   = _f(meters.get(METER_AC_POWER, 0))
    soc_raw    = _f(meters.get(METER_SOC, 0))
    cap_wh     = _f(meters.get(METER_CAPACITY_WH, 0))
    status_raw = str(meters.get(METER_STATUS, ""))
    mode_raw   = str(meters.get(METER_MODE, ""))

    return {
        "soc":             round(soc_raw / 10.0, 1),
        "capacity_wh":     round(cap_wh),
        "ac_input_power":  round(abs(ac_power), 1) if ac_power < 0 else 0.0,
        "ac_output_power": round(ac_power, 1)       if ac_power > 0 else 0.0,
        "status":          STATUS_LABELS.get(status_raw, status_raw) if status_raw else None,
        "mode":            MODE_LABELS.get(mode_raw,   mode_raw)   if mode_raw   else None,
        "mode_raw":        mode_raw,
    }


def _build_data_set(device_sn: str, dev_sn: str, key: str, value: str) -> bytes:
    payload = json.dumps({
        "cmd": "data_set",
        "gw_sn": device_sn,
        "timestamp": str(int(time.time() * 1000)),
        "info": {"dev_list": [{"dev_sn": dev_sn, "meter_list": [[key, value]]}]},
        "token": str(random.randint(100000000, 999999999)),
    }, separators=(",", ":")).encode()
    return bytes([0x4D, 0x00, 0x01, len(payload) & 0xFF]) + payload


class UltraJackCoordinator(DataUpdateCoordinator[dict[str, Any]]):

    def __init__(self, hass: HomeAssistant, config_data: dict) -> None:
        super().__init__(
            hass, _LOGGER,
            name=f"Ultra Jack {config_data.get(CONF_DEVICE_NAME, 'Unknown')}",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        self._address     = config_data[CONF_DEVICE_ADDRESS]
        self._device_name = config_data.get(CONF_DEVICE_NAME, "Ultra Jack")
        self._device_sn   = config_data.get(CONF_DEVICE_SN, "")
        self._dev_sn      = f"ems_{self._device_sn}"
        self._client: Optional[UltraJackBleClient] = None

    @property
    def device_name(self) -> str:
        return self._device_name

    @property
    def device_address(self) -> str:
        return self._address

    @property
    def device_sn(self) -> str:
        return self._device_sn

    async def _disconnect(self) -> None:
        if self._client:
            await self._client.disconnect()
            self._client = None

    async def _connect(self) -> None:
        ble_device = async_ble_device_from_address(
            self.hass, self._address, connectable=True
        )
        if not ble_device:
            raise UpdateFailed(f"Device {self._device_name} not found via HA Bluetooth")
        self._client = UltraJackBleClient(self._device_sn)
        bleak_client = await establish_connection(BleakClient, ble_device, self._device_name)
        if not await self._client.connect_with_client(bleak_client):
            self._client = None
            raise UpdateFailed(f"Failed to connect to {self._device_name}")

    async def _async_update_data(self) -> dict[str, Any]:
        await self._disconnect()
        try:
            await self._connect()
        except Exception as err:
            raise UpdateFailed(f"Connection error: {err}") from err

        try:
            response = await self._client.query_data(
                [str(m) for m in ALL_METER_IDS], timeout=12.0
            )
        finally:
            await self._disconnect()

        if response is None:
            if self.data:
                return self.data
            raise UpdateFailed("No response from device")

        info   = response.get("info", {})
        meters = _parse_meters(info)
        if not meters:
            if self.data:
                return self.data
            raise UpdateFailed("No meter readings in response")

        data = _build_sensor_data(meters)
        _LOGGER.debug("Sensor data: %s", data)
        return data

    async def async_send_command(self, key: str, value: str) -> None:
        """Send a data_set command then refresh.

        The device requires a device_get handshake before accepting data_set.
        """
        import asyncio
        from .ble_client import _build_device_get

        await self._disconnect()
        try:
            await self._connect()
        except Exception as err:
            raise RuntimeError(f"Connection error: {err}") from err
        try:
            # Step 1: device_get handshake (required before data_set)
            dg_packet = _build_device_get(self._device_sn)
            await self._client._client.write_gatt_char(CHAR_WRITE_UUID, dg_packet, response=False)
            await asyncio.sleep(0.5)

            # Step 2: data_set
            packet = _build_data_set(self._device_sn, self._dev_sn, key, value)
            _LOGGER.debug("data_set key=%s value=%s", key, value)
            await self._client._client.write_gatt_char(CHAR_WRITE_UUID, packet, response=False)
            await asyncio.sleep(0.5)
        finally:
            await self._disconnect()
        await self.async_request_refresh()

    async def async_shutdown(self) -> None:
        await self._disconnect()
