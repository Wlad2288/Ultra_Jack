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

## [1.1.0] - 2026-03-19

### Added Energy Dashboard Support
- Added new sensors "Energy Charged" and "Energy Discharged"
- Values are calculated in kWh based on changes of the actual capacity

## [1.1.1] - 2026-03-19

### Fixed
- Energy sensors (Energy Charged / Energy Discharged) no longer show a false
  spike after a Home Assistant restart. Previously, the first coordinator update
  after restart could add a large incorrect delta because the last known capacity
  was not properly seeded from restored state. The sensor now seeds
  `_last_capacity` from current coordinator data during initialisation and
  accumulates only real changes from that point forward.