"""Config flow for Ultra Jack Series integration."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_NAME,
    CONF_DEVICE_SN,
    HL_PREFIX,
)

_LOGGER = logging.getLogger(__name__)


def _extract_sn_from_name(name: str) -> str:
    """Extract serial number from BLE device name like 'Jackery_HL2B17900341HH9'."""
    prefix = "Jackery_"
    if name.startswith(prefix):
        return name[len(prefix):]
    return name


class UltraJackConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ultra Jack Series."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered_devices: dict[str, Any] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle bluetooth discovery."""
        name = discovery_info.name or ""
        if not name.startswith(HL_PREFIX):
            return self.async_abort(reason="not_ultra_jack")

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        _LOGGER.debug("Bluetooth discovery: %s (%s)", name, discovery_info.address)
        self.context["title_placeholders"] = {"name": name}
        self._discovered_devices[discovery_info.address] = {
            CONF_DEVICE_NAME: name,
            CONF_DEVICE_ADDRESS: discovery_info.address,
            CONF_DEVICE_SN: _extract_sn_from_name(name),
        }
        return await self.async_step_confirm()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step — scan for devices."""
        errors = {}

        if user_input is not None:
            address = user_input[CONF_DEVICE_ADDRESS]
            if address in self._discovered_devices:
                device_info = self._discovered_devices[address]
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=device_info[CONF_DEVICE_NAME],
                    data=device_info,
                )
            errors["base"] = "device_not_found"

        # Discover via HA Bluetooth
        self._discovered_devices = {}
        configured = self._async_current_ids(include_ignore=False)
        connectable_infos = list(async_discovered_service_info(self.hass, connectable=True))
        connectable_addrs = {i.address for i in connectable_infos}
        all_infos = list(async_discovered_service_info(self.hass, connectable=False))
        _LOGGER.debug(
            "HA Bluetooth knows %d device(s), %d connectable",
            len(all_infos), len(connectable_infos),
        )
        # Log every Jackery advertisement so users can report what their
        # device actually broadcasts (name, connectability).
        for svc_info in all_infos:
            name = svc_info.name or ""
            if "jackery" in name.lower():
                _LOGGER.debug(
                    "Seen Jackery device: name=%s address=%s connectable=%s rssi=%s",
                    name, svc_info.address,
                    svc_info.address in connectable_addrs, svc_info.rssi,
                )
                if name.startswith(HL_PREFIX) and svc_info.address not in connectable_addrs:
                    _LOGGER.debug(
                        "Skipping %s: only seen by non-connectable scanners "
                        "(passive adapter or proxy?)", name,
                    )

        for svc_info in connectable_infos:
            name = svc_info.name or ""
            if not name.startswith(HL_PREFIX) or svc_info.address in configured:
                continue
            self._discovered_devices[svc_info.address] = {
                CONF_DEVICE_NAME: name,
                CONF_DEVICE_ADDRESS: svc_info.address,
                CONF_DEVICE_SN: _extract_sn_from_name(name),
            }

        if not self._discovered_devices:
            _LOGGER.debug("No connectable %s* devices found", HL_PREFIX)
            return self.async_abort(reason="no_devices_found")

        device_options = {
            addr: f"{info[CONF_DEVICE_NAME]} ({addr})"
            for addr, info in self._discovered_devices.items()
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_DEVICE_ADDRESS): vol.In(device_options),
            }),
            errors=errors,
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovered device."""
        self._set_confirm_only()
        if user_input is not None:
            address = list(self._discovered_devices.keys())[0]
            device_info = self._discovered_devices[address]
            return self.async_create_entry(
                title=device_info[CONF_DEVICE_NAME],
                data=device_info,
            )

        name = list(self._discovered_devices.values())[0][CONF_DEVICE_NAME]
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"name": name},
        )
