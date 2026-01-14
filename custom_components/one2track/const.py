"""Constants for the One2Track integration."""

from datetime import timedelta
from logging import Logger, getLogger
from typing import Final

LOGGER: Logger = getLogger(__package__)

# Integration domain
DOMAIN: Final = "one2track"

# Default configuration
DEFAULT_PREFIX: Final = "one2track"
DEFAULT_UPDATE_RATE_MIN: Final = 1

# Time constants
CHECK_TIME_DELTA: Final = timedelta(hours=1, minutes=0)

# Configuration entry keys (lowercase per HA standards)
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"
CONF_ACCOUNT_ID: Final = "account_id"

# Platforms
PLATFORMS: Final = ["device_tracker"]

# Attribution
ATTRIBUTION: Final = "Data provided by One2Track"
