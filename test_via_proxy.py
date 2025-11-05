#!/usr/bin/env python3
"""
Test BLE connection to NordicTrack treadmill via ESPHome BLE Proxy
This script connects through the M5Stack BLE proxy device
"""

import asyncio
import logging
from aioesphomeapi import APIClient

# BLE Proxy configuration
PROXY_HOST = "192.168.2.9"
PROXY_PORT = 6053
PROXY_PASSWORD = ""  # ESPHome uses encryption key, not password
PROXY_ENCRYPTION_KEY = "EX1k2GYkbgzMjskMOTy9I4DG7c+lM3bAWs5T2guUvvQ="

# Treadmill configuration
TREADMILL_MAC = "DC:E3:FA:CF:00:91"  # Linux format MAC
TREADMILL_NAME = "I_TL"

# BLE Characteristics
CHAR_NOTIFY_1 = "00001535-1412-efde-1523-785feabcd123"  # Main data
CHAR_READ_1 = "00001534-1412-efde-1523-785feabcd123"    # Backup data

# Enable logging
logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)


async def test_via_proxy():
    """Test connection through BLE proxy"""

    print("="*70)
    print("NORDICTRACK TREADMILL - BLE PROXY CONNECTION TEST")
    print("="*70)
    print(f"Proxy: {PROXY_HOST}:{PROXY_PORT}")
    print(f"Target MAC: {TREADMILL_MAC}")
    print(f"Target Name: {TREADMILL_NAME}")
    print()

    # Step 1: Connect to ESPHome API
    print("[1/4] Connecting to ESPHome BLE Proxy...")
    client = APIClient(
        PROXY_HOST,
        PROXY_PORT,
        PROXY_PASSWORD,
        noise_psk=PROXY_ENCRYPTION_KEY
    )

    try:
        await client.connect(login=True)
        print(f"✅ Connected to BLE proxy")
        print()

        # Step 2: Get device info
        print("[2/4] Getting device info...")
        device_info = await client.device_info()
        print(f"✅ Device: {device_info.name}")
        print(f"   Model: {device_info.model}")
        print(f"   ESPHome Version: {device_info.esphome_version}")
        print()

        # Step 3: List Bluetooth devices
        print("[3/4] Scanning for Bluetooth devices...")

        # Subscribe to BLE advertisements
        found_treadmill = False
        treadmill_address = None

        def on_bluetooth_le_advertisement(data):
            nonlocal found_treadmill, treadmill_address
            if data.name == TREADMILL_NAME or data.address == TREADMILL_MAC:
                found_treadmill = True
                treadmill_address = data.address
                print(f"✅ Found treadmill: {data.name} at {data.address}")
                print(f"   RSSI: {data.rssi} dBm")

        await client.subscribe_bluetooth_le_advertisements(on_bluetooth_le_advertisement)

        # Wait for advertisements
        print("   Listening for advertisements (10 seconds)...")
        await asyncio.sleep(10)

        if not found_treadmill:
            print(f"❌ Treadmill not found")
            return False

        print()

        # Step 4: Connect to treadmill via proxy
        print("[4/4] Connecting to treadmill via proxy...")

        # Request connection
        connection_id = await client.bluetooth_device_connect(
            treadmill_address,
            timeout=15.0
        )

        print(f"✅ Connected! Connection ID: {connection_id}")
        print()

        # Read characteristic
        print("Reading BLE characteristics...")

        try:
            # Read characteristic by handle
            # Note: We may need service discovery first to get the correct handle
            print(f"   Attempting to read characteristic {CHAR_NOTIFY_1}...")
            print(f"   (Full BLE GATT operations via ESPHome proxy coming soon)")
            print()

        except Exception as e:
            print(f"⚠️  Error: {e}")

        # Disconnect
        await client.bluetooth_device_disconnect(treadmill_address)
        print("✅ Disconnected from treadmill")

        print()
        print("="*70)
        print("✅ TEST PASSED - BLE Proxy connection working!")
        print("="*70)
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        result = asyncio.run(test_via_proxy())
        exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted")
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
