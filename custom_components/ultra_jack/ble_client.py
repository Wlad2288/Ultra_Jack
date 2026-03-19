"""BLE Client for Jackery HL Series devices — v10.

Fragment protocol:
  0x14 continuation:  6-byte header, data = raw[6:]
  0x04 last (any):    4-byte header, data = raw[4:]

JSON extraction: scan assembled bytes for valid {..} JSON, robust to
boundary-crossing header bytes that may corrupt the stream.
"""

import asyncio
import json
import logging
import random
import time
from typing import Optional, Callable, Dict, Any

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

from .const import CHAR_WRITE_UUID, CHAR_NOTIFY_UUID, HL_PREFIX, CMD_DEVICE_GET, CMD_DATA_GET

_LOGGER = logging.getLogger(__name__)

HL_MARKER        = 0x4D
MSG_CONTINUATION = 0x14
MSG_LAST         = 0x04

INIT_METER_IDS = ["25753601", "25749505"]


def _ts() -> str:
    return str(int(time.time() * 1000))


def _token() -> str:
    return str(random.randint(100000000, 2000000000))


def _build_device_get(device_sn: str) -> bytes:
    payload = json.dumps(
        {"cmd": CMD_DEVICE_GET, "gw_sn": device_sn, "timestamp": _ts(), "info": {}},
        separators=(",", ":"),
    ).encode()
    return bytes([HL_MARKER, 0x00, 0x00, len(payload) & 0xFF]) + payload


def _build_data_get(device_sn: str, meter_ids: list, seq: int = 0) -> list:
    meter_list_json = json.dumps(meter_ids, separators=(",", ":"))
    payload_str = (
        '{"cmd":"data_get"'
        f',"gw_sn":"{device_sn}"'
        f',"timestamp":"{_ts()}"'
        f',"info":{{"dev_list":[{{"dev_sn":"ems_{device_sn}"'
        f',"meter_list":{meter_list_json}}}]}}'
        f',"token":"{_token()}"}}'
    )
    payload = payload_str.encode()
    n = len(payload)
    if n <= 250:
        return [bytes([HL_MARKER, 0x00, seq & 0xFF, n & 0xFF]) + payload]
    part1, part2 = payload[:250], payload[250:]
    pkt1 = bytes([HL_MARKER, 0x10, seq & 0xFF, 0xFC, n & 0xFF, (n >> 8) & 0xFF]) + part1
    pkt2 = bytes([HL_MARKER, 0x00, (seq + 1) & 0xFF, len(part2) & 0xFF]) + part2
    return [pkt1, pkt2]


def _extract_json(data: bytes) -> Optional[dict]:
    """
    Extract valid JSON object from potentially corrupt assembled bytes.
    Scans for matching { } pairs to handle header bytes injected at boundaries.
    """
    text = data.decode('utf-8', errors='replace')
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    # Try next occurrence
                    start = -1
                    depth = 0
    return None


class _Assembler:
    """
    Reassemble HL notification fragments.

    0x14 (continuation): 6-byte header, data = raw[6:]
    0x04 (last, any):    4-byte header, data = raw[4:]
    """

    def __init__(self, cb: Callable[[Dict[str, Any]], None]):
        self._cb  = cb
        self._buf: bytes = b""
        self._has_continuation = False

    def handle(self, raw: bytes) -> None:
        _LOGGER.debug("RAW NOTIFY %d bytes: %s...", len(raw), raw[:20].hex())

        if len(raw) == 5 and raw[0] == 0x49:
            _LOGGER.debug("  ACK, ignoring")
            return

        if len(raw) < 5 or raw[0] != HL_MARKER:
            self._try_fire(raw)
            return

        msg_id = raw[1]

        if msg_id == MSG_CONTINUATION:
            # 6-byte header
            chunk = raw[6:]
            _LOGGER.debug("  continuation chunk=%d: %s",
                          len(chunk), chunk[:60].decode('utf-8', 'replace'))
            self._buf += chunk
            self._has_continuation = True

        elif msg_id == MSG_LAST:
            # Always 4-byte header regardless of whether preceded by continuations
            chunk = raw[4:]
            if self._has_continuation:
                _LOGGER.debug("  last(multi) chunk=%d: %s",
                              len(chunk), chunk[:60].decode('utf-8', 'replace'))
                self._buf += chunk
            else:
                _LOGGER.debug("  last(single) chunk=%d: %s",
                              len(chunk), chunk[:60].decode('utf-8', 'replace'))
                self._buf = chunk

            _LOGGER.debug("  firing decoder (%d bytes)", len(self._buf))
            j = _extract_json(self._buf)
            if j:
                _LOGGER.debug("Decoded JSON cmd=%s (%d bytes)", j.get("cmd", "?"), len(self._buf))
                self._cb(j)
            else:
                _LOGGER.debug("JSON extraction failed, buf hex: %s", self._buf[:40].hex())

            self._buf = b""
            self._has_continuation = False
        else:
            _LOGGER.debug("  unknown msg_id=0x%02x", msg_id)

    def flush(self) -> None:
        if self._buf:
            j = _extract_json(self._buf)
            if j:
                self._cb(j)
        self._buf = b""
        self._has_continuation = False


class JackeryHLBleClient:
    def __init__(self, device_sn: str):
        self._sn    = device_sn
        self._client: Optional[BleakClient] = None
        self._asm:    Optional[_Assembler]  = None
        self._ev    = asyncio.Event()
        self._last: Optional[dict] = None

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    async def connect_with_client(self, client: BleakClient) -> bool:
        try:
            self._client = client
            self._asm    = _Assembler(self._on_msg)
            await self._client.start_notify(CHAR_NOTIFY_UUID, self._on_raw)
            _LOGGER.debug("HL client connected to %s", self._sn)
            return True
        except Exception as e:
            _LOGGER.error("connect_with_client failed: %s", e)
            self._client = None
            return False

    async def disconnect(self) -> None:
        if self._asm:
            self._asm.flush()
        if self._client:
            try:
                if self._client.is_connected:
                    try:
                        await self._client.stop_notify(CHAR_NOTIFY_UUID)
                    except Exception:
                        pass
                    await self._client.disconnect()
            except Exception:
                pass
        self._client = None

    def _on_raw(self, sender, data: bytes) -> None:
        if self._asm:
            self._asm.handle(bytes(data))

    def _on_msg(self, msg: dict) -> None:
        cmd = msg.get("cmd", "")
        _LOGGER.debug("Complete message: cmd=%s", cmd)
        if cmd == CMD_DATA_GET:
            info = msg.get("info", {})
            dev_list = info.get("dev_list", [])
            if dev_list:
                ml = dev_list[0].get("meter_list", [])
                if len(ml) > 5:
                    _LOGGER.debug("Accepting data_get response (%d meters)", len(ml))
                    self._last = msg
                    self._ev.set()

    async def query_data(self, all_meter_ids: list, timeout: float = 12.0) -> Optional[dict]:
        self._ev.clear()
        self._last = None

        _LOGGER.debug("Step 1: device_get")
        await self._write(_build_device_get(self._sn))
        await asyncio.sleep(0.15)

        _LOGGER.debug("Step 2: data_get init (2 IDs)")
        for p in _build_data_get(self._sn, INIT_METER_IDS, seq=1):
            await self._write(p)
        await asyncio.sleep(0.15)

        _LOGGER.debug("Step 3: data_get full (%d IDs)", len(all_meter_ids))
        pkts = _build_data_get(self._sn, all_meter_ids, seq=2)
        for i, p in enumerate(pkts):
            await self._write(p)
            if i < len(pkts) - 1:
                await asyncio.sleep(0.15)

        try:
            await asyncio.wait_for(self._ev.wait(), timeout)
            return self._last
        except asyncio.TimeoutError:
            _LOGGER.debug("query_data timeout after %.0fs", timeout)
            return None

    async def _write(self, data: bytes) -> None:
        if not self._client or not self._client.is_connected:
            raise RuntimeError("Not connected")
        _LOGGER.debug("WRITE %d bytes: %s...", len(data), data[:30].hex())
        await self._client.write_gatt_char(CHAR_WRITE_UUID, data, response=False)


async def scan_hl_devices(timeout: float = 10.0) -> list:
    found = {}
    def cb(dev: BLEDevice, adv):
        name = dev.name or ""
        if name.startswith(HL_PREFIX) and dev.address not in found:
            found[dev.address] = dev
    s = BleakScanner(detection_callback=cb)
    await s.start()
    await asyncio.sleep(timeout)
    await s.stop()
    return list(found.values())
