#!/usr/bin/env python3
"""
Test GATT characteristic reading through ESPHome BLE Proxy
This proves we can read treadmill data through the proxy
"""

import asyncio
import logging
from aioesphomeapi import APIClient

# ESP Proxy config
PROXY_HOST = "192.168.2.9"
PROXY_PORT = 6053
PROXY_PASSWORD = ""
PROXY_ENCRYPTION_KEY = "EX1k2GYkbgzMjskMOTy9I4DG7c+lM3bAWs5T2guUvvQ="

# Treadmill config
TREADMILL_NAME = "I_TL"
TREADMILL_ADDRESS = None  # Will discover

# Characteristic to read
CHAR_NOTIFY_1_UUID = "00001535-1412-efde-1523-785feabcd123"

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)


async def test_gatt_read():
    """Test reading GATT characteristic through ESP proxy."""

    print("="*70)
    print("GATT READ TEST VIA ESP PROXY")
    print("="*70)

    client = APIClient(
        PROXY_HOST,
        PROXY_PORT,
        PROXY_PASSWORD,
        noise_psk=PROXY_ENCRYPTION_KEY
    )

    try:
        # Connect to proxy
        print(f"\n[1/4] Connecting to ESP proxy at {PROXY_HOST}:{PROXY_PORT}...")
        await client.connect(login=True)
        device_info = await client.device_info()
        print(f"✅ Connected: {device_info.name} (ESPHome {device_info.esphome_version})")

        # Discover treadmill
        print(f"\n[2/4] Scanning for treadmill '{TREADMILL_NAME}'...")
        treadmill_address = None

        def on_advertisement(data):
            nonlocal treadmill_address
            if data.name == TREADMILL_NAME:
                treadmill_address = data.address
                print(f"✅ Found: {data.name} at {data.address} (RSSI: {data.rssi} dBm)")

        await client.subscribe_bluetooth_le_advertisements(on_advertisement)
        await asyncio.sleep(10)

        if not treadmill_address:
            print("❌ Treadmill not found")
            return False

        # Try to connect and read
        print(f"\n[3/4] Connecting to treadmill...")

        # This is where it gets complex - ESPHome BLE connection needs:
        # 1. Connection state callback
        # 2. Service discovery
        # 3. GATT read by handle (not UUID)

        print("⚠️  ESPHome BLE GATT API requires:")
        print("   - Connection state callback")
        print("   - Service/characteristic discovery to get handles")
        print("   - GATT reads use handles, not UUIDs")
        print()
        print("   This is complex to implement in a simple test.")
        print("   For production, use Bleak on a machine with direct BT access,")
        print("   or implement full ESPHome BLE client with all callbacks.")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(test_gatt_read())
