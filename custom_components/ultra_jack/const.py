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

# Confirmed meter IDs from raw data analysis
# 16934913: AC power flow W (negative = grid input, positive = grid output)
# 21548033: SOC × 10  (480 = 48.0%)
# 21549057: Available capacity Wh (985 = 985 Wh)

METER_AC_POWER    = 16934913   # AC power W (signed: - = input, + = output)
METER_SOC         = 21548033   # SOC × 10
METER_CAPACITY_WH = 21549057   # Available capacity Wh

# All 18 meter IDs (must be sent in this exact order)
ALL_METER_IDS = [
    "23132161", "21545985", "21534721", "21535745",
    "16932865", "16933889", "16937985", "21541889",
    "16935937", "16934913", "21547009", "16930817",
    "16936961", "21548033", "21549057", "21542913",
    "21556225", "21552129",
]
