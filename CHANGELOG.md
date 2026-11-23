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

## [1.5.0] - 2026-04-06

### Added
- Solar energy sensor — cumulative kWh from DC/PV input power, 
  for use in the HA Energy Dashboard as solar production source.
  Relevant for users with solar panels connected directly to the 
  DC input of the power station.

## [1.5.1] - 2026-11-23

Maintenance release — bug fixes and internal cleanup only, no new entities.

### Fixed
- Energy sensors (charged / discharged / loss / solar) no longer reset to 0
  when Home Assistant restarts or the integration reloads while the device is
  unavailable (e.g. switched off). The counter value is now stored separately
  from the entity state (`RestoreSensor`).
- Energy sensors no longer keep accumulating stale power values while the
  device is unreachable (cached data was integrated again on every poll).
- Polling and commands are now serialised with a lock — a button press or
  mode change during a poll could tear down the other connection.
- Coordinator shutdown now calls the base implementation (refresh timer was
  not cancelled) and is no longer run twice on unload.
- Failed commands now raise a visible error in the UI instead of a bare `RuntimeError`.
- Loss sensor re-seeds capacity after long gaps instead of counting the delta.

### Changed
- Transient BLE failures: last values are kept for up to 5 consecutive failed
  polls, after which entities become unavailable (previously cached values
  were shown indefinitely, while a single connection error made everything unavailable).
- Already configured devices are hidden in the manual setup dialog.
- Packet framing unified in `ble_client.py` (frames are byte-identical to 1.5.0);
  `data_set` now supports multiple values per command. Removed unused `BleakScanner` code.
- Device model shown as "HL Series" (also covers HomePower devices).

## [1.6.0] - 2026-11-23

Feature release — tooling to resolve open issues. Includes all fixes from 1.5.1.

### Added
- **Diagnostics download** (Settings → Devices & Services → Ultra Jack → ⋮ →
  Download diagnostics) including the raw meter map — helps identify unknown
  meter IDs such as per-string PV values (#7). Serial number, name and
  address are redacted.
- Detailed debug logging in the setup dialog: every Jackery advertisement seen
  by HA Bluetooth is logged with connectability and RSSI, plus the reason a
  device was skipped (#8).
