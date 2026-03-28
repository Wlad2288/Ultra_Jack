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

## [1.2.0] - 2026-03-20

### Added
- **Energy Loss sensor** — tracks standby losses and self-discharge separately
  from real discharge. Capacity decreases while AC output is idle (≤ 10 W) are
  now counted as losses instead of being attributed to the discharge sensor.
  This prevents standby consumption from appearing as grid feed-in in the
  Home Assistant Energy Dashboard.

### Changed
- **Energy Discharged** now only accumulates when AC output power exceeds 10 W,
  ensuring only real loads are counted.
- Energy sensors now ignore capacity deltas larger than 200 Wh per poll cycle
  to prevent false accumulation after the device was offline or restarted.
- Energy sensor state is correctly restored after a Home Assistant restart —
  previously the accumulated value could reset to 0 if the device was
  unreachable at startup.

## [1.3.0] - 2026-03-20

### Added
- **Status select** — dropdown to set device status (`Normal` / `Standby`)
- **Operating mode select** — dropdown to set operating mode (`Backup` / `Self-consumption` / `Battery priority` / `Time-based`)
- **Status sensor** — reads current status from device (`23133185`)
- **Operating mode sensor** — reads current operating mode from device (`23132161`)
- Unknown values are displayed as their raw code (e.g. `"6"`) for future identification

### Changed
- All entity names are now in English
- `23133185` added to polled meter IDs so the status sensor is populated correctly
- `data_set` commands now perform a `device_get` handshake before writing, matching the official app behaviour

## [1.3.1] - 2026-03-20

### Added
- **Status sensor** — shows `Active` or `Auto standby` based on meter `21552129`
- **Awake button** — wakes the device from auto standby (`23133185=2`)

### Removed
- Status dropdown — the Operating mode sensor already reflects standby state

## [1.4.0] - 2026-03-29

### Added
- DC input power sensor (meter 16932865) — shows current PV/DC charging power in watts

### Fixed  
- Connection timing for slower devices: client now waits for device_get 
  response before sending data_get instead of fixed 150ms delay