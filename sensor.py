"""NordicTrack Treadmill sensor platform - Direct ESPHome Proxy (WORKING)."""
import logging
import asyncio
from datetime import timedelta

from aioesphomeapi import APIClient, APIConnectionError
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

# ESPHome BLE Proxy configuration
PROXY_HOST = "192.168.2.9"
PROXY_PORT = 6053
PROXY_PASSWORD = ""
PROXY_ENCRYPTION_KEY = "EX1k2GYkbgzMjskMOTy9I4DG7c+lM3bAWs5T2guUvvQ="

# BLE Characteristic UUID
CHAR_NOTIFY_1_UUID = "00001535-1412-efde-1523-785feabcd123"

# Polling interval
POLL_INTERVAL = timedelta(seconds=30)


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

    # Set up active poller via ESPHome proxy
    coordinator = TreadmillESPProxyCoordinator(hass, sensors)
    await coordinator.async_start()

    _LOGGER.info("NordicTrack Treadmill initialized (ESP proxy direct connection)")


class TreadmillESPProxyCoordinator:
    """Coordinator to poll treadmill directly via ESPHome BLE proxy."""

    def __init__(self, hass: HomeAssistant, sensors: list):
        """Initialize the coordinator."""
        self.hass = hass
        self.sensors = {sensor.sensor_type: sensor for sensor in sensors}
        self._cancel_callback = None
        self._previous_values = {}
        self._esp_client = None
        self._treadmill_address = None
        self._char_handle = None
        self._disconnect_callback = None
        self._is_connected = False

    async def async_start(self):
        """Start active polling via ESP proxy."""
        _LOGGER.info("Connecting to ESP proxy at %s:%s", PROXY_HOST, PROXY_PORT)

        # Connect to ESP proxy
        self._esp_client = APIClient(
            PROXY_HOST,
            PROXY_PORT,
            PROXY_PASSWORD,
            noise_psk=PROXY_ENCRYPTION_KEY
        )

        try:
            await self._esp_client.connect(login=True)
            device_info = await self._esp_client.device_info()
            _LOGGER.info("Connected to ESP proxy: %s (ESPHome %s)",
                        device_info.name, device_info.esphome_version)

            # Subscribe to BLE advertisements to find treadmill
            def on_advertisement(data):
                if data.name == TREADMILL_NAME and not self._treadmill_address:
                    self._treadmill_address = data.address
                    _LOGGER.info("Found treadmill at address: %s", self._treadmill_address)

            # This returns a callback (unsub function), don't await it
            self._esp_client.subscribe_bluetooth_le_advertisements(on_advertisement)

            # Wait for treadmill discovery
            _LOGGER.info("Scanning for treadmill...")
            await asyncio.sleep(10)

            if not self._treadmill_address:
                _LOGGER.warning("Treadmill not found, will retry on next poll")
                self._update_sensor_availability(False)

            # Start polling
            self._cancel_callback = async_track_time_interval(
                self.hass,
                self._async_poll_treadmill,
                POLL_INTERVAL,
            )

            # Do first poll immediately
            await self._async_poll_treadmill(None)

        except Exception as e:
            _LOGGER.error("Failed to connect to ESP proxy: %s", e)
            self._update_sensor_availability(False)

    async def _async_poll_treadmill(self, now):
        """Poll treadmill for current data via ESP proxy."""
        if not self._esp_client or not self._treadmill_address:
            _LOGGER.debug("ESP client or treadmill address not ready")
            return

        try:
            # Connect to treadmill if not connected
            if not self._is_connected:
                _LOGGER.debug("Connecting to treadmill...")
                connected = asyncio.Event()

                def on_connection_state(is_connected, mtu, error):
                    self._is_connected = is_connected
                    if is_connected:
                        _LOGGER.debug("Connected (MTU: %d)", mtu)
                        connected.set()
                    elif error:
                        _LOGGER.warning("Connection error: %d", error)

                self._disconnect_callback = await self._esp_client.bluetooth_device_connect(
                    self._treadmill_address,
                    on_connection_state,
                    timeout=30.0
                )

                try:
                    await asyncio.wait_for(connected.wait(), timeout=15.0)
                except asyncio.TimeoutError:
                    _LOGGER.warning("Connection timeout")
                    self._update_sensor_availability(False)
                    return

                # Discover services to get characteristic handle
                if not self._char_handle:
                    _LOGGER.debug("Discovering GATT services...")
                    services = await self._esp_client.bluetooth_gatt_get_services(
                        self._treadmill_address
                    )

                    for service in services.services:
                        for char in service.characteristics:
                            if char.uuid.lower() == CHAR_NOTIFY_1_UUID.lower():
                                self._char_handle = char.handle
                                _LOGGER.info("Found target characteristic (handle: %d)", self._char_handle)
                                break

                    if not self._char_handle:
                        _LOGGER.error("Target characteristic not found")
                        self._update_sensor_availability(False)
                        return

            # Read characteristic
            _LOGGER.debug("Reading characteristic...")
            data = await self._esp_client.bluetooth_gatt_read(
                self._treadmill_address,
                self._char_handle,
                timeout=10.0
            )

            _LOGGER.debug("Read %d bytes", len(data))
            self._parse_and_update(data)
            self._update_sensor_availability(True)

        except Exception as e:
            _LOGGER.error("Error polling treadmill: %s", e, exc_info=True)
            self._is_connected = False
            self._char_handle = None
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
            _LOGGER.debug("Message type: 0x%02x %02x (not telemetry - treadmill idle?)",
                         msg_type, msg_subtype)

    def _update_sensor_availability(self, available: bool):
        """Update availability of all sensors."""
        for sensor in self.sensors.values():
            sensor.set_available(available)

    async def async_stop(self):
        """Stop polling and disconnect."""
        if self._cancel_callback:
            self._cancel_callback()
        if self._is_connected and self._disconnect_callback:
            try:
                await self._esp_client.bluetooth_device_disconnect(self._treadmill_address)
                self._disconnect_callback()
            except:
                pass
        if self._esp_client:
            await self._esp_client.disconnect()
        _LOGGER.info("Stopped ESP proxy polling")


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
