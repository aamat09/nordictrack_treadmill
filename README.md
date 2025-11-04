# NordicTrack Treadmill Integration for Home Assistant

Monitor your NordicTrack T5 treadmill telemetry in Home Assistant via Bluetooth!

## Features

- 📊 **Real-time monitoring** of treadmill data
- 🏃 **Speed** (mph)
- ⛰️ **Incline** (%)
- 📏 **Distance** (miles)
- ⏱️ **Time** (seconds)
- 🔥 **Calories** burned
- 🎯 **Status** (running/idle)

## Requirements

- Home Assistant with Bluetooth support
- **BLE Proxy** (ESP32 running ESPHome bluetooth_proxy)
  - Your M5Stack at 192.168.2.9 works perfectly!
- NordicTrack treadmill within Bluetooth range

## Installation

### Method 1: Manual Installation

1. **Copy the integration** to your Home Assistant:
   ```bash
   cd /Users/aamat/Downloads
   scp -r nordictrack_treadmill <user>@<ha-host>:/config/custom_components/
   ```

2. **Add to configuration.yaml**:
   ```yaml
   # NordicTrack Treadmill
   nordictrack_treadmill:
   ```

3. **Restart Home Assistant**

4. **Check logs** for "NordicTrack Treadmill integration loaded"

### Method 2: HACS (Future)

Once you publish to GitHub, users can install via HACS.

## Configuration

No configuration needed! The integration automatically:
- Discovers your treadmill via Bluetooth
- Listens for BLE notifications from your M5Stack proxy
- Creates sensor entities

## Sensors Created

The integration creates these sensors:

- `sensor.nordictrack_speed` - Current speed in mph
- `sensor.nordictrack_incline` - Current incline in %
- `sensor.nordictrack_distance` - Total distance in miles
- `sensor.nordictrack_time` - Workout time in seconds
- `sensor.nordictrack_calories` - Calories burned
- `sensor.nordictrack_status` - running or idle

## How It Works

```
NordicTrack Treadmill (I_TL)
        ↓ BLE Notifications
M5Stack BLE Proxy (192.168.2.9)
        ↓ ESPHome API
Home Assistant Core
        ↓ Bluetooth Events
NordicTrack Integration
        ↓ Decodes Data
Sensor Entities
```

## Example Dashboard Card

```yaml
type: entities
title: Treadmill
entities:
  - entity: sensor.nordictrack_status
    name: Status
  - entity: sensor.nordictrack_speed
    name: Speed
  - entity: sensor.nordictrack_incline
    name: Incline
  - entity: sensor.nordictrack_distance
    name: Distance
  - entity: sensor.nordictrack_time
    name: Time
  - entity: sensor.nordictrack_calories
    name: Calories
```

## Troubleshooting

### Sensors not updating?

1. **Check BLE proxy is running**:
   - Your M5Stack at 192.168.2.9 should be online
   - Check ESPHome logs: `esphome logs m5stack_lite_s3_treadmill_ble_proxy.yaml`

2. **Check treadmill is broadcasting**:
   - Turn on the treadmill
   - Check HA Bluetooth integrations for "I_TL"

3. **Enable debug logging**:
   ```yaml
   logger:
     logs:
       custom_components.nordictrack_treadmill: debug
   ```

4. **Check Home Assistant logs**:
   ```
   Settings → System → Logs
   Search for "nordictrack"
   ```

### Treadmill disconnects?

The treadmill may have a timeout. This is normal - the integration will reconnect automatically when it starts broadcasting again.

## Protocol Details

See `/Users/aamat/m5stack/TREADMILL_PROTOCOL.md` for technical details about the BLE protocol.

## Contributing

Found a bug? Have suggestions? Open an issue on GitHub!

## Credits

- Reverse engineered using PacketLogger and Bleak
- BLE protocol analysis with nRF Connect and ESPHome
- Built with ❤️ for the Home Assistant community

## License

MIT License - feel free to use and modify!
