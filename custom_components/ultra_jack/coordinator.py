"""DataUpdateCoordinator for Ultra Jack."""

import asyncio
import logging
import time
from datetime import timedelta
from typing import Any, Optional

from bleak import BleakClient
from bleak_retry_connector import establish_connection

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN, CONF_DEVICE_ADDRESS, CONF_DEVICE_NAME, CONF_DEVICE_SN,
    DEFAULT_UPDATE_INTERVAL, ALL_METER_IDS, MAX_FAILED_POLLS,
    METER_AC_POWER, METER_DC_POWER, METER_SOC, METER_CAPACITY_WH,
    METER_MODE, METER_SLEEP,
    MODE_LABELS, SLEEP_LABELS,
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
    dc_power   = _f(meters.get(METER_DC_POWER, 0))
    soc_raw    = _f(meters.get(METER_SOC, 0))
    cap_wh     = _f(meters.get(METER_CAPACITY_WH, 0))
    mode_raw  = str(meters.get(METER_MODE, ""))
    sleep_raw = str(meters.get(METER_SLEEP, ""))

    status = SLEEP_LABELS.get(sleep_raw, sleep_raw) if sleep_raw else None

    return {
        "soc":             round(soc_raw / 10.0, 1),
        "capacity_wh":     round(cap_wh),
        "ac_input_power":  round(abs(ac_power), 1) if ac_power < 0 else 0.0,
        "ac_output_power": round(ac_power, 1)       if ac_power > 0 else 0.0,
        "dc_input_power":  round(dc_power, 1)        if dc_power > 0 else 0.0,
        "status":          status,
        "mode":            MODE_LABELS.get(mode_raw, mode_raw) if mode_raw else None,
        "mode_raw":        mode_raw,
        # Monotonic timestamp of this reading. Energy sensors use it to avoid
        # integrating the same (stale) power value more than once.
        "updated_at":      time.monotonic(),
    }


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
        self._client: Optional[UltraJackBleClient] = None
        # Serialises BLE access: polling and commands must never share/tear
        # down each other's connection.
        self._ble_lock = asyncio.Lock()
        self._failed_polls = 0

    @property
    def device_name(self) -> str:
        return self._device_name

    @property
    def device_address(self) -> str:
        return self._address

    @property
    def device_sn(self) -> str:
        return self._device_sn

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            name=self._device_name,
            manufacturer="Jackery",
            model="HL Series",
            serial_number=self._device_sn,
        )

    async def _disconnect(self) -> None:
        if self._client:
            await self._client.disconnect()
            self._client = None

    async def _connect(self) -> UltraJackBleClient:
        ble_device = async_ble_device_from_address(
            self.hass, self._address, connectable=True
        )
        if not ble_device:
            raise ConnectionError(f"Device {self._device_name} not found via HA Bluetooth")
        client = UltraJackBleClient(self._device_sn)
        bleak_client = await establish_connection(BleakClient, ble_device, self._device_name)
        if not await client.connect_with_client(bleak_client):
            try:
                await bleak_client.disconnect()
            except Exception:  # noqa: BLE001
                pass
            raise ConnectionError(f"Failed to start notifications on {self._device_name}")
        self._client = client
        return client

    async def _poll(self) -> dict[int, Any]:
        async with self._ble_lock:
            await self._disconnect()
            try:
                client = await self._connect()
                response = await client.query_data(
                    [str(m) for m in ALL_METER_IDS], timeout=12.0
                )
            finally:
                await self._disconnect()

        if response is None:
            raise UpdateFailed("No response from device")
        meters = _parse_meters(response.get("info", {}))
        if not meters:
            raise UpdateFailed("No meter readings in response")
        return meters

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            meters = await self._poll()
        except Exception as err:  # noqa: BLE001
            self._failed_polls += 1
            # Tolerate a few transient BLE failures by keeping the last values
            # (with their original timestamp, so energy sensors don't integrate
            # stale power). Beyond that, mark entities unavailable.
            if self.data and self._failed_polls < MAX_FAILED_POLLS:
                _LOGGER.debug(
                    "Poll failed (%d/%d), keeping last values: %s",
                    self._failed_polls, MAX_FAILED_POLLS, err,
                )
                return self.data
            if isinstance(err, UpdateFailed):
                raise
            raise UpdateFailed(f"Connection error: {err}") from err

        self._failed_polls = 0
        data = _build_sensor_data(meters)
        _LOGGER.debug("Sensor data: %s", data)
        return data

    async def async_send_command(self, key: str, value: str) -> None:
        """Send a single data_set command, then refresh."""
        await self.async_send_values([[key, value]])

    async def async_send_values(self, pairs: list[list[str]]) -> None:
        """Send one or more [meter_id, value] pairs via data_set, then refresh."""
        async with self._ble_lock:
            await self._disconnect()
            try:
                client = await self._connect()
                await client.set_values(pairs)
            except Exception as err:  # noqa: BLE001
                raise HomeAssistantError(
                    f"Failed to send command to {self._device_name}: {err}"
                ) from err
            finally:
                await self._disconnect()
        await self.async_request_refresh()

    async def async_shutdown(self) -> None:
        await super().async_shutdown()
        await self._disconnect()
