# Installation Guide

## Quick Start

### Step 1: Copy Integration to Home Assistant

**Option A: Direct Copy (if HA is on same network)**

```bash
# From your Mac
cd /Users/aamat/Downloads
scp -r nordictrack_treadmill root@192.168.2.6:/config/custom_components/
```

**Option B: Manual Copy**

1. Zip the folder:
   ```bash
   cd /Users/aamat/Downloads
   zip -r nordictrack_treadmill.zip nordictrack_treadmill/
   ```

2. Transfer to Home Assistant:
   - Use Samba/SMB to access `/config/custom_components/`
   - Or use Home Assistant File Editor add-on
   - Or use SSH/SCP

3. Extract in `/config/custom_components/`

### Step 2: Add to Configuration

Edit `/config/configuration.yaml` and add:

```yaml
# NordicTrack Treadmill Integration
nordictrack_treadmill:
```

### Step 3: Restart Home Assistant

1. Go to **Settings** → **System** → **Restart**
2. Or use Developer Tools → YAML → Restart

### Step 4: Verify Installation

Check the logs:
1. **Settings** → **System** → **Logs**
2. Search for "NordicTrack"
3. You should see: "NordicTrack Treadmill integration loaded"

### Step 5: Check Sensors

1. Go to **Settings** → **Devices & Services**
2. Search for "NordicTrack" entities
3. Or go to **Developer Tools** → **States**
4. Filter by "nordictrack"

You should see:
- `sensor.nordictrack_speed`
- `sensor.nordictrack_incline`
- `sensor.nordictrack_distance`
- `sensor.nordictrack_time`
- `sensor.nordictrack_calories`
- `sensor.nordictrack_status`

### Step 6: Test It!

1. **Turn on your treadmill**
2. **Start walking/running**
3. **Watch the sensors update in real-time!** 🎉

## Troubleshooting

### Integration not loading?

**Check file structure:**
```
/config/custom_components/nordictrack_treadmill/
├── __init__.py
├── const.py
├── manifest.json
├── sensor.py
└── README.md
```

**Check logs for errors:**
```
Settings → System → Logs
```

### Sensors showing "unavailable"?

1. **Make sure M5Stack BLE proxy is running**:
   - Check `192.168.2.9` is online
   - M5Stack should have `bluetooth_proxy: active: true`

2. **Make sure treadmill is on**:
   - The treadmill must be powered on
   - BLE name should be "I_TL"

3. **Check Bluetooth integration**:
   - Settings → Devices & Services → Bluetooth
   - Should show detected devices

### Need more debug info?

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.nordictrack_treadmill: debug
    homeassistant.components.bluetooth: debug
```

Then restart and check logs!

## Next Steps

Once it's working, you can:

1. **Create dashboard cards** (see README.md)
2. **Set up automations** (e.g., notify when workout is done)
3. **Track fitness stats** over time
4. **Share on GitHub** to help others!

## Need Help?

- Check Home Assistant logs
- Review `/Users/aamat/m5stack/TREADMILL_PROTOCOL.md`
- Open an issue on GitHub

Happy monitoring! 🏃‍♂️📊
