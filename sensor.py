"""NordicTrack Treadmill sensor platform."""
import logging
from datetime import timedelta

from homeassistant.components import bluetooth
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

SCAN_INTERVAL = timedelta(seconds=1)


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

    # Set up BLE listener
    coordinator = TreadmillBLECoordinator(hass, sensors)
    await coordinator.async_start()

    _LOGGER.info("NordicTrack Treadmill sensors initialized")


class TreadmillBLECoordinator:
    """Coordinator to handle BLE notifications from treadmill."""

    def __init__(self, hass: HomeAssistant, sensors: list):
        """Initialize the coordinator."""
        self.hass = hass
        self.sensors = {sensor.sensor_type: sensor for sensor in sensors}
        self._cancel_callback = None

    async def async_start(self):
        """Start listening for BLE notifications."""

        @callback
        def _async_bluetooth_callback(
            service_info: bluetooth.BluetoothServiceInfoBleak,
            change: bluetooth.BluetoothChange,
        ) -> None:
            """Handle bluetooth notifications."""

            # Check if this is our treadmill
            if service_info.name != TREADMILL_NAME:
                return

            _LOGGER.debug(
                "BLE callback: %s - %s - RSSI: %s",
                service_info.name,
                service_info.address,
                service_info.rssi,
            )

            # Check for service data or manufacturer data
            if service_info.service_data:
                for uuid, data in service_info.service_data.items():
                    _LOGGER.debug("Service data from %s: %s", uuid, data.hex())
                    self._parse_notification(data)

            if service_info.manufacturer_data:
                for manufacturer_id, data in service_info.manufacturer_data.items():
                    _LOGGER.debug("Manufacturer data %s: %s", manufacturer_id, data.hex())

        # Register BLE callback
        self._cancel_callback = bluetooth.async_register_callback(
            self.hass,
            _async_bluetooth_callback,
            bluetooth.BluetoothCallbackMatcher(
                address=None,  # Listen to all, filter by name
                connectable=False,
            ),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )

        _LOGGER.info("Started BLE listener for treadmill")

    def _parse_notification(self, data: bytes):
        """Parse treadmill notification data."""

        if len(data) < 2:
            return

        hex_data = data.hex()
        _LOGGER.debug("Parsing notification: %s (%d bytes)", hex_data, len(data))

        msg_type = data[0]
        msg_subtype = data[1] if len(data) > 1 else 0

        # Parse based on message patterns we discovered

        # Type: 00 12 - Main telemetry
        if msg_type == 0x00 and msg_subtype == 0x12 and len(data) >= 10:
            # Bytes 4-5: Speed (in 0.1 mph increments)
            if len(data) >= 6:
                speed_raw = (data[5] << 8) | data[4]
                speed = speed_raw / 10.0
                if 0 <= speed <= 20:  # Sanity check
                    self.sensors[SENSOR_SPEED].update_value(speed)
                    _LOGGER.debug("Speed: %.1f mph", speed)

            # Bytes 6-7: Incline (in 0.5% increments)
            if len(data) >= 8:
                incline_raw = (data[7] << 8) | data[6]
                incline = incline_raw / 10.0
                if 0 <= incline <= 15:  # Sanity check
                    self.sensors[SENSOR_INCLINE].update_value(incline)
                    _LOGGER.debug("Incline: %.1f%%", incline)

            # Update status
            if speed > 0:
                self.sensors[SENSOR_STATUS].update_value("running")
            else:
                self.sensors[SENSOR_STATUS].update_value("idle")

        # Type: 01 12 - Extended telemetry (distance, time, calories)
        elif msg_type == 0x01 and msg_subtype == 0x12 and len(data) >= 10:
            # Try to extract distance/time/calories
            # This will need refinement based on actual data
            _LOGGER.debug("Extended telemetry packet")

        # Type: FE 02 - Status message
        elif msg_type == 0xFE and msg_subtype == 0x02:
            _LOGGER.debug("Status message")

    async def async_stop(self):
        """Stop listening for BLE notifications."""
        if self._cancel_callback:
            self._cancel_callback()
        _LOGGER.info("Stopped BLE listener")


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

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True
