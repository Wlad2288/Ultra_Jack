"""Constants for Ultra Jack Series integration."""

DOMAIN = "ultra_jack"

CONF_DEVICE_ADDRESS = "device_address"
CONF_DEVICE_NAME    = "device_name"
CONF_DEVICE_SN      = "device_sn"

DEFAULT_UPDATE_INTERVAL = 30

SERVICE_UUID     = "0000ffff-0000-1000-8000-00805f9b34fb"
CHAR_WRITE_UUID  = "0000ff01-0000-1000-8000-00805f9b34fb"
CHAR_NOTIFY_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"

HL_PREFIX = "Jackery_HL"

CMD_DEVICE_GET = "device_get"
CMD_DATA_GET   = "data_get"
CMD_DATA_SET   = "data_set"

# Meter IDs
METER_AC_POWER    = 16934913
METER_DC_POWER    = 16932865  # DC/PV input power W
METER_SOC         = 21548033
METER_CAPACITY_WH = 21549057
METER_MODE        = 23132161  # Operating mode  → Mode sensor
METER_SLEEP       = 21552129  # Sleep state: 0=active, 5=auto standby

ALL_METER_IDS = [
    "23132161", "21545985", "21534721", "21535745",
    "16932865", "16933889", "16937985", "21541889",
    "16935937", "16934913", "21547009", "16930817",
    "16936961", "21548033", "21549057", "21542913",
    "21556225", "21552129", "23133185",
]

# Mode labels (23132161)
# Unknown values are shown as their raw code, e.g. "6"
MODE_LABELS = {
    "1": "Backup",
    "2": "Self-consumption",
    "3": "Battery priority",
    "4": "Time-based",
    "5": "Standby",
}

# Sleep state labels (21552129)
SLEEP_LABELS = {
    "0": "Active",
    "5": "Auto standby",
}

# Select options (writable modes)
MODE_OPTIONS = {
    "Backup":            "1",
    "Self-consumption":  "2",
    "Battery priority":  "3",
    "Time-based":        "4",
}
MODE_OPTIONS_INV = {v: k for k, v in MODE_OPTIONS.items()}
