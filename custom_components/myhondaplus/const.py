import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "myhondaplus"

CONF_REFRESH_TOKEN = "refresh_token"
CONF_ACCESS_TOKEN = "access_token"
CONF_PERSONAL_ID = "personal_id"
CONF_USER_ID = "user_id"
CONF_VIN = "vin"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_DEVICE_KEY_PEM = "device_key_pem"
CONF_VEHICLE_NAME = "vehicle_name"
CONF_FUEL_TYPE = "fuel_type"

DEFAULT_SCAN_INTERVAL = 600  # 10 minutes
DEFAULT_TRIP_INTERVAL = 3600  # 1 hour
