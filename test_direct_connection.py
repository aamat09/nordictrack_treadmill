#!/usr/bin/env python3
"""
Test direct BLE connection to NordicTrack treadmill
Run this on a machine with Bluetooth to verify connectivity
"""

import asyncio
from bleak import BleakClient, BleakScanner

# Treadmill configuration
TREADMILL_MAC = "DC:E3:FA:CF:00:91"
TREADMILL_NAME = "I_TL"

# BLE Characteristics
CHAR_NOTIFY_1 = "00001535-1412-efde-1523-785feabcd123"  # Main data (73 bytes)
CHAR_READ_1 = "00001534-1412-efde-1523-785feabcd123"    # Backup data


async def test_connection():
    """Test direct connection to treadmill"""

    print("="*70)
    print("NORDICTRACK TREADMILL CONNECTION TEST")
    print("="*70)
    print(f"Target MAC: {TREADMILL_MAC}")
    print(f"Target Name: {TREADMILL_NAME}")
    print()

    # Step 1: Scan for treadmill
    print("[1/3] Scanning for treadmill (10 seconds)...")
    device = await BleakScanner.find_device_by_address(TREADMILL_MAC, timeout=10.0)

    if not device:
        print(f"❌ Treadmill not found at {TREADMILL_MAC}")
        print("\nTrying scan by name...")
        device = await BleakScanner.find_device_by_name(TREADMILL_NAME, timeout=10.0)

        if not device:
            print(f"❌ Treadmill '{TREADMILL_NAME}' not found")
            print("\nDiscovered devices:")
            devices = await BleakScanner.discover(timeout=5.0)
            for d in devices:
                print(f"  - {d.name or 'Unknown'} ({d.address})")
            return False

    print(f"✅ Found treadmill: {device.name} at {device.address}")
    print()

    # Step 2: Connect
    print("[2/3] Connecting to treadmill...")
    try:
        async with BleakClient(device, timeout=15.0) as client:
            if not client.is_connected:
                print("❌ Failed to connect")
                return False

            print(f"✅ Connected!")
            print()

            # Step 3: Read characteristics
            print("[3/3] Reading BLE characteristics...")

            try:
                data = await client.read_gatt_char(CHAR_NOTIFY_1)
                print(f"✅ Read CHAR_NOTIFY_1: {len(data)} bytes")
                print(f"   Hex: {data.hex()}")
                print(f"   Raw: {list(data)}")
                print()

                # Parse data
                if len(data) >= 10:
                    msg_type = data[0]
                    msg_subtype = data[1]
                    print(f"   Message Type: 0x{msg_type:02x} {msg_subtype:02x}")

                    if msg_type == 0x00 and msg_subtype == 0x12:
                        # Speed (bytes 4-5)
                        speed_raw = (data[5] << 8) | data[4]
                        speed = speed_raw / 10.0
                        print(f"   Speed: {speed:.1f} mph")

                        # Incline (bytes 6-7)
                        if len(data) >= 8:
                            incline_raw = (data[7] << 8) | data[6]
                            incline = incline_raw / 10.0
                            print(f"   Incline: {incline:.1f}%")

            except Exception as e:
                print(f"⚠️  Error reading CHAR_NOTIFY_1: {e}")

            try:
                data = await client.read_gatt_char(CHAR_READ_1)
                print(f"\n✅ Read CHAR_READ_1: {len(data)} bytes")
                print(f"   Hex: {data.hex()}")
            except Exception as e:
                print(f"\n⚠️  Error reading CHAR_READ_1: {e}")

            print()
            print("="*70)
            print("✅ TEST PASSED - Treadmill connection working!")
            print("="*70)
            return True

    except Exception as e:
        print(f"❌ Connection error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        result = asyncio.run(test_connection())
        exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted")
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
