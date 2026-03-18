# Ultra Jack

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/YOUR_GITHUB_USERNAME/ultra_jack.svg)](https://github.com/YOUR_GITHUB_USERNAME/ultra_jack/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Home Assistant integration for Jackery HL-series portable power stations.**

Communicates directly over **Bluetooth Low Energy** — no cloud, no Jackery account, no internet connection required.

> Protocol reverse-engineered from HCI snoop logs of the official Jackery Home app.  
> Tested on the **Jackery Explorer 2000 Ultra**.

---

## Features

- 🔋 **SOC** — battery state of charge (%)
- ⚡ **Available Capacity** — usable energy remaining (Wh)
- 🔌 **AC Input Power** — power drawn from the grid / charging (W)
- 🏠 **AC Output Power** — power delivered to connected loads (W)
- 📡 **Fully local** — no cloud, works offline
- 🔍 **Auto-discovery** — scans for nearby HL-series devices automatically
- 🌐 **ESP32 Bluetooth Proxy** supported — no direct BT adapter needed on HA host
- 🔄 **Reliable polling** — reconnects every cycle, sensors never go stale

---

## Supported Devices

| Device | Status |
|--------|--------|
| Jackery Explorer 2000 Ultra | ✅ Tested |
| Other Jackery HL-series (`Jackery_HL*`) | 🔶 Should work — untested |

Meter IDs and device serial numbers are discovered dynamically from the `device_get`
response — no hardcoded device-specific values.

---

## Requirements

- Home Assistant 2023.8.0 or newer
- Bluetooth adapter reachable by HA **or** an [ESP32 Bluetooth Proxy](https://esphome.io/projects/?type=bluetooth)
- Device must not be connected to the Jackery Home app simultaneously

---

## Installation via HACS (recommended)

1. Open HACS → **Integrations** → ⋮ → **Custom repositories**
2. Add `https://github.com/YOUR_GITHUB_USERNAME/ultra_jack` → Category: **Integration**
3. Search for **Ultra Jack** → **Download**
4. Restart Home Assistant
5. **Settings → Devices & Services → Add Integration → Ultra Jack**

## Manual Installation

1. Download the [latest release](https://github.com/YOUR_GITHUB_USERNAME/ultra_jack/releases/latest) ZIP
2. Extract and copy the `ultra_jack` folder to `/config/custom_components/ultra_jack/`
3. Restart Home Assistant
4. **Settings → Devices & Services → Add Integration → Ultra Jack**

---

## Sensors

| Sensor | Unit | Notes |
|--------|------|-------|
| SOC | % | State of charge |
| Available Capacity | Wh | Usable energy remaining |
| AC Input Power | W | Grid input / charging power |
| AC Output Power | W | Power delivered to loads |

---

## Bluetooth Setup

### ESP32 Bluetooth Proxy (recommended)

Flash an ESP32 (e.g. M5Stack ATOM Lite) via browser at  
👉 https://esphome.io/projects/?type=bluetooth  
Place it near the Jackery. It acts as a wireless BLE bridge for HA.

### USB Bluetooth Adapter

Plug a USB adapter directly into the HA host. Use adapters based on the **CSR8510A10** chip.  
> ⚠️ Use a **USB 2.0** port — USB 3.0 causes 2.4 GHz interference.

---

## Troubleshooting

**Device not found during setup**  
→ Power on the Jackery, close the Jackery Home app, stay within BT range (~10m).

**Sensors show old values**  
→ The integration reconnects every 30s poll cycle. Check HA logs for BLE errors.

**Enable debug logging:**
```yaml
logger:
  default: info
  logs:
    custom_components.ultra_jack: debug
```

---

## Technical Background

The Jackery HL-series uses a custom JSON protocol over BLE characteristics
`0xFF01` (write) / `0xFF02` (notify) within service `0xFFFF`.

Fully reverse-engineered by capturing HCI snoop logs from Android while the
official Jackery Home app communicated with a Jackery Explorer 2000 Ultra.

Key findings:
- No encryption — plain JSON over BLE
- 3-step handshake per poll: `device_get` → `data_get` (init) → `data_get` (full)
- Custom multi-fragment protocol for large notifications
- Device stops responding if BLE session stays open → reconnect every cycle
- Meter IDs and `dev_sn` discovered dynamically from `device_get` response

---

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgements

Inspired by [private_jack](https://github.com/porcupin26/private_jack) for older Jackery models.
