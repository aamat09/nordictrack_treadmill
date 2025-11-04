"""Constants for NordicTrack Treadmill integration."""

DOMAIN = "nordictrack_treadmill"

# Treadmill BLE identifiers
TREADMILL_NAME = "I_TL"
TREADMILL_MAC = "DC:E3:FA:CF:00:91"

# BLE Service and Characteristics
SERVICE_UUID = "00001533-1412-efde-1523-785feabcd123"
NOTIFY_CHAR_UUID = "00001535-1412-efde-1523-785feabcd123"
WRITE_CHAR_UUID = "00001534-1412-efde-1523-785feabcd123"

# Sensor types
SENSOR_SPEED = "speed"
SENSOR_INCLINE = "incline"
SENSOR_DISTANCE = "distance"
SENSOR_TIME = "time"
SENSOR_CALORIES = "calories"
SENSOR_STATUS = "status"

# Update interval
SCAN_INTERVAL = 1  # seconds
