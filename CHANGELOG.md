# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-03-18

### Added
- Initial release
- Support for Jackery Explorer 2000 Ultra (HL-series BLE devices)
- Auto-discovery of nearby HL-series devices via Bluetooth
- Dynamic meter ID discovery from `device_get` response — no hardcoded device values
- 4 sensors: SOC (%), Available Capacity (Wh), AC Input Power (W), AC Output Power (W)
- Works with ESP32 Bluetooth Proxy — no direct Bluetooth adapter required on HA host
- Keeps last known sensor values during transient BLE communication failures

### Protocol
- Developed by capturing BLE traffic between the official app and the device using standard debugging tools
- Pure local BLE communication — no cloud, no Jackery account required
- Supports Jackery HL-series devices (BLE name prefix `Jackery_HL`)

## [1.0.1] - 2026-03-18

### Fixed
- HACS Validation