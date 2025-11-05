"""NordicTrack Treadmill sensor platform - Active Polling via Proxy."""
import logging
import asyncio
from datetime import timedelta

from homeassistant.components import bluetooth
from bleak import BleakClient
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfSpeed,
    UnitOfLength,
    UnitOfTime,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    TREADMILL_NAME,
    TREADMILL_MAC,
    SERVICE_UUID,
    NOTIFY_CHAR_UUID,
    SENSOR_SPEED,
    SENSOR_INCLINE,
    SENSOR_DISTANCE,
    SENSOR_TIME,
    SENSOR_CALORIES,
    SENSOR_STATUS,
)

_LOGGER = logging.getLogger(__name__)

# BLE Characteristics to read
CHAR_NOTIFY_1 = "00001535-1412-efde-1523-785feabcd123"  # Main data (73 bytes)

# Polling intervals
POLL_INTERVAL = timedelta(seconds=30)  # Poll every 30 seconds


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the NordicTrack Treadmill sensors."""

    # Create sensor entities
    sensors = [
        NordicTrackSensor(hass, SENSOR_SPEED, "Speed", "mdi:speedometer", UnitOfSpeed.MILES_PER_HOUR),
        NordicTrackSensor(hass, SENSOR_INCLINE, "Incline", "mdi:angle-acute", PERCENTAGE),
        NordicTrackSensor(hass, SENSOR_DISTANCE, "Distance", "mdi:map-marker-distance", UnitOfLength.MILES),
        NordicTrackSensor(hass, SENSOR_TIME, "Time", "mdi:timer-outline", UnitOfTime.SECONDS),
        NordicTrackSensor(hass, SENSOR_CALORIES, "Calories", "mdi:fire", "cal"),
        NordicTrackSensor(hass, SENSOR_STATUS, "Status", "mdi:run", None),
    ]

    async_add_entities(sensors, True)

    # Set up active poller
    coordinator = TreadmillBLECoordinator(hass, sensors)
    await coordinator.async_start()

    _LOGGER.info("NordicTrack Treadmill sensors initialized (active polling)")


class TreadmillBLECoordinator:
    """Coordinator to actively poll treadmill via BLE through HA bluetooth/proxy."""

    def __init__(self, hass: HomeAssistant, sensors: list):
        """Initialize the coordinator."""
        self.hass = hass
        self.sensors = {sensor.sensor_type: sensor for sensor in sensors}
        self._cancel_callback = None
        self._previous_values = {}

    async def async_start(self):
        """Start active polling."""
        _LOGGER.info("Starting active BLE polling (30 second interval)")

        # Do first poll immediately
        await self._async_poll_treadmill(None)

        # Schedule periodic polling
        self._cancel_callback = async_track_time_interval(
            self.hass,
            self._async_poll_treadmill,
            POLL_INTERVAL,
        )

    async def _async_poll_treadmill(self, now):
        """Poll treadmill for current data through HA bluetooth."""
        try:
            # Get BLE device from Home Assistant's bluetooth
            # This will use whatever backend is available (local BT or ESP proxy)
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, TREADMILL_MAC, connectable=True
            )

            if not ble_device:
                _LOGGER.debug("Treadmill not found via bluetooth discovery")
                self._update_sensor_availability(False)
                return

            _LOGGER.debug("Connecting to treadmill via HA bluetooth...")

            # Connect using Bleak (HA will route through proxy if needed)
            async with BleakClient(ble_device, timeout=15.0) as client:
                if not client.is_connected:
                    _LOGGER.warning("Failed to connect to treadmill")
                    self._update_sensor_availability(False)
                    return

                _LOGGER.debug("Connected! Reading characteristics...")

                # Read main characteristic
                data = await client.read_gatt_char(CHAR_NOTIFY_1)
                _LOGGER.info("Read %d bytes from treadmill", len(data))

                # Parse and update
                self._parse_and_update(data)
                self._update_sensor_availability(True)

        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout connecting to treadmill")
            self._update_sensor_availability(False)
        except Exception as e:
            _LOGGER.error("Error polling treadmill: %s", e, exc_info=True)
            self._update_sensor_availability(False)

    def _parse_and_update(self, data: bytes):
        """Parse treadmill data and update sensors."""

        if len(data) < 2:
            return

        hex_data = data.hex()
        _LOGGER.debug("Data: %s", hex_data)

        msg_type = data[0]
        msg_subtype = data[1] if len(data) > 1 else 0

        # Type: 00 12 - Main telemetry
        if msg_type == 0x00 and msg_subtype == 0x12 and len(data) >= 10:
            # Bytes 4-5: Speed (in 0.1 mph increments)
            if len(data) >= 6:
                speed_raw = (data[5] << 8) | data[4]
                speed = speed_raw / 10.0
                if 0 <= speed <= 20:  # Sanity check
                    if self._previous_values.get(SENSOR_SPEED) != speed:
                        _LOGGER.info("Speed: %.1f mph", speed)
                    self._previous_values[SENSOR_SPEED] = speed
                    self.sensors[SENSOR_SPEED].update_value(speed)

            # Bytes 6-7: Incline (in 0.5% increments)
            if len(data) >= 8:
                incline_raw = (data[7] << 8) | data[6]
                incline = incline_raw / 10.0
                if 0 <= incline <= 15:  # Sanity check
                    if self._previous_values.get(SENSOR_INCLINE) != incline:
                        _LOGGER.info("Incline: %.1f%%", incline)
                    self._previous_values[SENSOR_INCLINE] = incline
                    self.sensors[SENSOR_INCLINE].update_value(incline)

            # Update status
            status = "running" if speed > 0 else "idle"
            if self._previous_values.get(SENSOR_STATUS) != status:
                _LOGGER.info("Status: %s", status)
            self._previous_values[SENSOR_STATUS] = status
            self.sensors[SENSOR_STATUS].update_value(status)
        else:
            _LOGGER.debug("Message type: 0x%02x %02x (not telemetry)", msg_type, msg_subtype)

    def _update_sensor_availability(self, available: bool):
        """Update availability of all sensors."""
        for sensor in self.sensors.values():
            sensor.set_available(available)

    async def async_stop(self):
        """Stop polling."""
        if self._cancel_callback:
            self._cancel_callback()
        _LOGGER.info("Stopped BLE polling")


class NordicTrackSensor(SensorEntity):
    """Representation of a NordicTrack Treadmill sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        sensor_type: str,
        name: str,
        icon: str,
        unit: str | None,
    ):
        """Initialize the sensor."""
        self.hass = hass
        self.sensor_type = sensor_type
        self._attr_name = f"NordicTrack {name}"
        self._attr_unique_id = f"nordictrack_treadmill_{sensor_type}"
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = (
            SensorStateClass.MEASUREMENT
            if sensor_type != SENSOR_STATUS
            else None
        )
        self._attr_native_value = None

        # Set device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "nordictrack_t5")},
            "name": "NordicTrack T5 Treadmill",
            "manufacturer": "NordicTrack",
            "model": "T5",
        }

    @callback
    def update_value(self, value):
        """Update the sensor value."""
        self._attr_native_value = value
        self.async_write_ha_state()

    @callback
    def set_available(self, available: bool):
        """Set sensor availability."""
        self._attr_available = available
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return getattr(self, "_attr_available", True)
