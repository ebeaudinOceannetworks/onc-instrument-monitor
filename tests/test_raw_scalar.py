# tests/debug_oxygen_raw.py
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Path bootstrap to locate the root core utilities folder
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.onc_client import ONCClient
from core.registry import load_yaml

def debug_sensor_streams():
    client = ONCClient()
    device_code = "SBE63633706"
    
    print("=" * 95)
    print(f"📡 DIRECT ONC ENDPOINT AUDIT FOR DEVICE: {device_code}")
    print("=" * 95)

    end = datetime.now(timezone.utc)
    start_24h = end - timedelta(hours=24)
    start_1h = end - timedelta(hours=1)

    # Test Pass 1: Standard 24-Hour Clean (Our working baseline)
    print("\n1️⃣ Checking 24-Hour Clean Data Payload Structure:")
    print("-" * 95)
    try:
        clean_params = {
            "deviceCode": device_code,
            "dateFrom": start_24h.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "dateTo": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "resamplePeriod": 900,
            "qualityControl": "clean"
        }
        clean_payload = client._onc.getScalardataByDevice(clean_params)
        sensor_data = clean_payload.get("sensorData", [])
        print(f"  🟢 Success! Server returned payload keys: {list(clean_payload.keys())}")
        print(f"  🔹 Streams Found: {len(sensor_data)}")
        if sensor_data:
            vals = sensor_data[0].get("data", {}).get("values", [])
            print(f"  🔹 Data Points in first stream: {len(vals)}")
    except Exception as e:
        print(f"  ❌ Clean 24h Pass Failed: {e}")

    # Test Pass 2: 24-Hour Raw Data (The problematic blank chart)
    print("\n2️⃣ Checking 24-Hour Raw Data Payload Size Limit:")
    print("-" * 95)
    try:
        raw_params_24h = {
            "deviceCode": device_code,
            "dateFrom": start_24h.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "dateTo": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "qualityControl": "raw"
        }
        raw_payload_24h = client._onc.getScalardataByDevice(raw_params_24h)
        sensor_data_raw = raw_payload_24h.get("sensorData", [])
        print(f"  🟢 Payload Received! Keys: {list(raw_payload_24h.keys())}")
        if sensor_data_raw:
            vals = sensor_data_raw[0].get("data", {}).get("values", [])
            print(f"  🔹 Total Un-resampled Raw Points (24h): {len(vals)}")
        else:
            print("  ⚠️ Server returned an empty container for 24h raw data.")
    except Exception as e:
        print(f"  ❌ Raw 24h Server Query Rejected: {e}")

    # Test Pass 3: 1-Hour Narrow-Window Raw Data (Checking size constraints)
    print("\n3️⃣ Checking 1-Hour Narrow-Window Raw Data:")
    print("-" * 95)
    try:
        raw_params_1h = {
            "deviceCode": device_code,
            "dateFrom": start_1h.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "dateTo": end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "qualityControl": "raw"
        }
        raw_payload_1h = client._onc.getScalardataByDevice(raw_params_1h)
        sensor_data_1h = raw_payload_1h.get("sensorData", [])
        if sensor_data_1h:
            vals = sensor_data_1h[0].get("data", {}).get("values", [])
            print(f"  🎉 Narrow window found data! Points in last hour: {len(vals)}")
        else:
            print("  ⚪ Narrow window is also completely empty.")
    except Exception as e:
        print(f"  ❌ Raw 1h Failure: {e}")
        
    print("=" * 95)

if __name__ == "__main__":
    debug_sensor_streams()