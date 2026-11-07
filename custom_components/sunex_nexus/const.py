"""Integration constants; no installation-specific configuration."""
from homeassistant.const import Platform

DOMAIN = "sunex_nexus"
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.NUMBER,
             Platform.SELECT, Platform.SWITCH, Platform.BUTTON]
CONF_ALLOW_WRITES = "allow_writes"
CONF_EXCLUSIVE = "exclusive_gateway"
CONF_INTERVAL = "poll_interval"
DEFAULT_PORT = 10003
DEFAULT_INTERVAL = 30
OPERATING_FIELDS = {"enabled": (0, 1), "powerful": (1, 16), "silent": (1, 32),
                    "weather_compensation": (1, 64), "holiday": (2, 2)}
BINARY_KEYS = ("enabled", "compressor_running", "fan_running", "pump_running",
               "defrost", "flow_switch_closed", "evu_contact_closed", "sg_contact_closed")
