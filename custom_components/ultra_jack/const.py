"""Constants for Ultra Jack integration."""

DOMAIN = "ultra_jack"

CONF_DEVICE_ADDRESS = "device_address"
CONF_DEVICE_NAME    = "device_name"
CONF_DEVICE_SN      = "device_sn"

DEFAULT_UPDATE_INTERVAL = 30  # seconds

# BLE UUIDs for Jackery HL-series
SERVICE_UUID     = "0000ffff-0000-1000-8000-00805f9b34fb"
CHAR_WRITE_UUID  = "0000ff01-0000-1000-8000-00805f9b34fb"
CHAR_NOTIFY_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"

# BLE device name prefix shared by all HL-series devices
HL_PREFIX = "Jackery_HL"

# Protocol commands
CMD_DEVICE_GET = "device_get"
CMD_DATA_GET   = "data_get"

# Known meter IDs confirmed on Explorer 2000 Ultra (HL-series)
# Meter values are discovered dynamically from device_get response,
# but these constants are used for parsing the data_get response.
METER_AC_POWER    = 16934913  # AC power W  (negative=input, positive=output)
METER_SOC         = 21548033  # SOC × 10   (480 = 48.0 %)
METER_CAPACITY_WH = 21549057  # Available capacity in Wh
