#!/usr/bin/env python3
"""
Complete test: Read treadmill data via ESPHome BLE Proxy
This demonstrates the full workflow for the integration
"""

import asyncio
import logging
from aioesphomeapi import APIClient

# Configuration
PROXY_HOST = "192.168.2.9"
PROXY_PORT = 6053
PROXY_PASSWORD = ""
PROXY_ENCRYPTION_KEY = "EX1k2GYkbgzMjskMOTy9I4DG7c+lM3bAWs5T2guUvvQ="

TREADMILL_NAME = "I_TL"
CHAR_NOTIFY_1_UUID = "00001535-1412-efde-1523-785feabcd123"

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)


async def main():
    """Main test flow."""

    print("="*70)
    print("COMPLETE TREADMILL DATA READ VIA ESP PROXY")
    print("="*70)

    client = APIClient(PROXY_HOST, PROXY_PORT, PROXY_PASSWORD, noise_psk=PROXY_ENCRYPTION_KEY)

    try:
        # Step 1: Connect to proxy
        print(f"\n[1/6] Connecting to ESP proxy...")
        await client.connect(login=True)
        device_info = await client.device_info()
        print(f"✅ {device_info.name} (ESPHome {device_info.esphome_version})")

        # Step 2: Find treadmill
        print(f"\n[2/6] Scanning for treadmill '{TREADMILL_NAME}'...")
        treadmill_address = None

        def on_adv(data):
            nonlocal treadmill_address
            if data.name == TREADMILL_NAME and not treadmill_address:
                treadmill_address = data.address
                print(f"✅ Found at address: {treadmill_address}")

        await client.subscribe_bluetooth_le_advertisements(on_adv)
        await asyncio.sleep(10)

        if not treadmill_address:
            print("❌ Treadmill not found")
            return False

        # Step 3: Connect to treadmill
        print(f"\n[3/6] Connecting to treadmill...")
        connected = asyncio.Event()

        def on_connection_state(is_connected, mtu, error):
            print(f"   Connection state: connected={is_connected}, mtu={mtu}, error={error}")
            if is_connected:
                connected.set()

        disconnect_callback = await client.bluetooth_device_connect(
            treadmill_address,
            on_connection_state,
            timeout=30.0
        )

        # Wait for connection
        try:
            await asyncio.wait_for(connected.wait(), timeout=15.0)
            print("✅ Connected")
        except asyncio.TimeoutError:
            print("❌ Connection timeout")
            return False

        # Step 4: Get GATT services
        print(f"\n[4/6] Discovering GATT services...")
        services = await client.bluetooth_gatt_get_services(treadmill_address)

        print(f"✅ Found {len(services.services)} services:")
        char_handle = None

        for service in services.services:
            print(f"   Service: {service.uuid}")
            for char in service.characteristics:
                print(f"      Characteristic: {char.uuid} (handle: {char.handle})")
                if char.uuid.lower() == CHAR_NOTIFY_1_UUID.lower():
                    char_handle = char.handle
                    print(f"         ⭐ This is our target characteristic!")

        if not char_handle:
            print(f"❌ Target characteristic {CHAR_NOTIFY_1_UUID} not found")
            return False

        # Step 5: Read characteristic
        print(f"\n[5/6] Reading characteristic (handle {char_handle})...")
        data = await client.bluetooth_gatt_read(treadmill_address, char_handle, timeout=10.0)

        print(f"✅ Read {len(data)} bytes")
        print(f"   Hex: {data.hex()}")
        print(f"   Raw: {list(data)}")

        # Step 6: Parse data
        print(f"\n[6/6] Parsing treadmill data...")
        if len(data) >= 2:
            msg_type = data[0]
            msg_subtype = data[1]
            print(f"   Message type: 0x{msg_type:02x} {msg_subtype:02x}")

            if msg_type == 0x00 and msg_subtype == 0x12 and len(data) >= 10:
                speed_raw = (data[5] << 8) | data[4]
                speed = speed_raw / 10.0
                print(f"   ✅ Speed: {speed:.1f} mph")

                if len(data) >= 8:
                    incline_raw = (data[7] << 8) | data[6]
                    incline = incline_raw / 10.0
                    print(f"   ✅ Incline: {incline:.1f}%")

                status = "running" if speed > 0 else "idle"
                print(f"   ✅ Status: {status}")
            else:
                print(f"   ℹ️  Not telemetry data (treadmill may be idle)")

        # Disconnect
        print(f"\n[7/6] Disconnecting...")
        await client.bluetooth_device_disconnect(treadmill_address)
        disconnect_callback()
        print("✅ Disconnected")

        print("\n" + "="*70)
        print("✅ TEST PASSED - Can read treadmill data via ESP proxy!")
        print("="*70)
        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await client.disconnect()


if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)
