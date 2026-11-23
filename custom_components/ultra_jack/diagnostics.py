"""Diagnostics for Ultra Jack.

Download via Settings → Devices & Services → Ultra Jack → ⋮ → Download diagnostics.
The raw meter map helps identify unknown meter IDs (e.g. per-string PV values).
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_DEVICE_ADDRESS, CONF_DEVICE_NAME, CONF_DEVICE_SN, ALL_METER_IDS
from .coordinator import UltraJackCoordinator

TO_REDACT = {CONF_DEVICE_ADDRESS, CONF_DEVICE_NAME, CONF_DEVICE_SN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: UltraJackCoordinator = hass.data[DOMAIN][entry.entry_id]
    data = dict(coordinator.data or {})
    data.pop("updated_at", None)
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "sensor_data": data,
        "requested_meter_ids": ALL_METER_IDS,
        "raw_meters": {str(k): v for k, v in sorted(coordinator.raw_meters.items())},
    }
