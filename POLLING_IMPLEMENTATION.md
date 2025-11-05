# NordicTrack Active Polling Implementation

## Overview
Changed the integration from **passive BLE listening** to **active BLE polling** with adaptive polling intervals.

## Key Changes Made

### 1. Polling Strategy
- **Default**: Polls treadmill every **30 seconds**
- **Adaptive**: Switches to **5-minute** intervals when no changes detected
- **Smart**: Returns to 30-second polling when changes are detected again

### 2. Modified Files

#### `sensor.py`
- **Removed**: `bluetooth` component imports (no longer passive listening)
- **Added**: `bleak` imports for direct BLE connection (`BleakClient`, `BleakScanner`)
- **Added**: `async_track_time_interval` for scheduling polls

**Key characteristics being read**:
```python
CHAR_NOTIFY_1 = "00001535-1412-efde-1523-785feabcd123"  # Main data (73 bytes)
CHAR_READ_1 = "00001534-1412-efde-1523-785feabcd123"    # Backup data
```

**TreadmillBLECoordinator changes**:
- `async_start()`: Schedules first poll immediately, then periodic polling
- `_async_poll_treadmill()`:
  - Scans for treadmill by name "I_TL"
  - Connects via BleakClient
  - Reads CHAR_NOTIFY_1
  - Parses data and detects changes
  - Adjusts polling interval based on changes
- `_parse_and_update()`: Returns `True` if any sensor values changed
- `_update_sensor_availability()`: Sets all sensors available/unavailable

**NordicTrackSensor changes**:
- Added `set_available()` method to allow coordinator to update availability
- Modified `available` property to check `_attr_available`

#### `manifest.json`
- **Changed**: `iot_class` from "local_push" to "local_polling"
- **Added**: `bleak>=0.21.0` to requirements
- **Bumped**: version to 2.0.0

### 3. How It Works

```
┌─────────────────────────────────────────────────┐
│  1. Integration starts                          │
│  2. Coordinator scans for "I_TL" treadmill      │
│  3. Finds device, stores address                │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│  Every 30 seconds (default):                    │
│  1. Connect to treadmill via BleakClient        │
│  2. Read characteristic CHAR_NOTIFY_1           │
│  3. Parse speed, incline, status                │
│  4. Compare with previous values                │
└────────────────────┬────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          │                     │
    Changes detected?     No changes?
          │                     │
          ▼                     ▼
   Keep 30s polling      Switch to 5min polling
```

### 4. Data Parsing
The integration parses byte data from the treadmill:

**Message Type: 00 12 (Main Telemetry)**
- Bytes 4-5: Speed (little-endian, 0.1 mph units)
  - Example: `0x0064` = 100 = 10.0 mph
- Bytes 6-7: Incline (little-endian, 0.1% units)
  - Example: `0x001E` = 30 = 3.0%
- Status: "running" if speed > 0, else "idle"

### 5. Error Handling
- **Timeout**: If connection fails, resets address to force rescan
- **Connection failure**: Marks all sensors as unavailable
- **Not found**: Logs debug message, sensors stay unavailable until found

## Deployment Instructions

### On Home Assistant Server

1. **Copy integration to custom_components**:
```bash
# From Mac to Home Assistant SMB share
cp -r ~/Downloads/nordictrack_treadmill /Volumes/config/custom_components/
```

2. **Restart Home Assistant**:
```bash
ssh root@192.168.2.7
docker restart homeassistant
```

3. **Monitor logs**:
```bash
docker logs -f homeassistant | grep -i nordictrack
```

### Expected Log Output

**Initial startup**:
```
INFO NordicTrack Treadmill integration loaded
INFO Starting active BLE polling for treadmill
DEBUG Scanning for treadmill...
INFO Found treadmill at DC:E3:FA:CF:00:91
DEBUG Connecting to treadmill...
DEBUG Connected! Reading characteristics...
INFO Data changed: 00120000640000001e00...
```

**When changes detected**:
```
INFO Speed changed: 5.0 mph
INFO Incline changed: 3.0%
INFO Adjusting poll interval to 30 seconds (changes: True)
```

**When idle (no changes)**:
```
DEBUG Connected! Reading characteristics...
INFO Adjusting poll interval to 5 minutes (changes: False)
```

## Configuration in Home Assistant

Add to `configuration.yaml`:
```yaml
nordictrack_treadmill:
```

That's it! No other configuration needed. The integration will:
1. Auto-discover the treadmill via BLE
2. Create 6 sensor entities:
   - `sensor.nordictrack_speed`
   - `sensor.nordictrack_incline`
   - `sensor.nordictrack_distance` (not yet implemented)
   - `sensor.nordictrack_time` (not yet implemented)
   - `sensor.nordictrack_calories` (not yet implemented)
   - `sensor.nordictrack_status`

## Testing Checklist

- [ ] Integration loads without errors
- [ ] Sensors created (check Developer Tools > States)
- [ ] Treadmill discovered and connected
- [ ] Speed sensor updates when treadmill running
- [ ] Incline sensor updates when incline changed
- [ ] Status changes from "idle" to "running"
- [ ] Polling interval adjusts (check logs)
- [ ] Sensors mark unavailable when treadmill off
- [ ] Sensors recover when treadmill turns on

## Future Enhancements

1. **Parse extended telemetry** (message type 01 12):
   - Distance
   - Time
   - Calories

2. **Add configuration options**:
   - Customize polling intervals
   - Set treadmill MAC address manually

3. **Add config flow**:
   - UI-based setup instead of yaml

4. **Bi-directional control**:
   - Send commands to treadmill (speed, incline)
   - Requires authentication protocol implementation

## Troubleshooting

### Sensors show "unavailable"
- Check treadmill is powered on
- Check Bluetooth is enabled on Home Assistant host
- Check logs for connection errors

### Polling too frequent/infrequent
- Edit constants in `sensor.py`:
  ```python
  POLL_INTERVAL_ACTIVE = timedelta(seconds=30)  # Adjust active polling
  POLL_INTERVAL_IDLE = timedelta(minutes=5)     # Adjust idle polling
  ```

### Connection timeouts
- Increase timeout in `_async_poll_treadmill()`:
  ```python
  async with BleakClient(self._treadmill_address, timeout=30.0) as client:
  ```

## GitHub Repository
https://github.com/aamat09/nordictrack_treadmill

## Version History
- **v1.0.0**: Initial passive BLE listening implementation
- **v2.0.0**: Active polling with adaptive intervals
