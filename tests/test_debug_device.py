# tests/test_debug_device.py
import sys
import os
from pathlib import Path

# Path bootstrap to locate the root core utilities
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.db import get_jb_info_for_device, get_db_connection
from core.registry import load_yaml

# Let's target the exact active CTD from your screenshot
TEST_DEVICE_ID = 23582

print("=" * 60)
print(f"🎯 TARGET DIAGNOSTIC FOR DEVICE ID: {TEST_DEVICE_ID}")
print("=" * 60)

# --- 1. TEST JINJA STATUS LOOKUP DICTIONARY ---
print("\nChecking Global Status Label Mapping Configuration:")
try:
    status_labels = load_yaml("status_rules.yaml").get("labels", {})
    print(f" -> Found status labels configuration keys: {list(status_labels.keys())}")
    for key, val in status_labels.items():
        print(f"    - [{key}]: Color={val.get('color')}, Display={val.get('display')}")
except Exception as e:
    print(f" ❌ Failed to read status_rules.yaml: {e}")

# --- 2. TEST RAW SQL DATA RETRIEVAL ---
print("\nExecuting sql/jb_status.sql against DB Matrix:")
try:
    raw_rows = get_jb_info_for_device(TEST_DEVICE_ID)
    if not raw_rows:
        print(" ⚠️ DB returned 0 rows for this device topology. Check if junction box is linked.")
    else:
        print(f" 🎉 Found {len(raw_rows)} database sensor tracks connected to this device:")
        print("-" * 60)
        for i, row in enumerate(raw_rows, 1):
            print(f" Row #{i}:")
            print(f"   - Device Code:  {row.get('devicecode')}")
            print(f"   - Sensor Code:  {row.get('sensorcode')}")
            print(f"   - Raw Value:    {row.get('sensor_value')} (Type: {type(row.get('sensor_value')).__name__})")
        print("-" * 60)
except Exception as e:
    print(f" ❌ SQL Execution failure: {e}")

print("\nDiagnostic completed.")