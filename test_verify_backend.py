#!/usr/bin/env python3
"""Targeted diagnostic to verify exactly why checklist_html returns empty."""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Initialize project paths & environment variables
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from core.onc_client import ONCClient
from workflows.commissioning_hydrophone import get_hydrophone_checklist_ui

def run_diagnostic():
    # 💡 Match this to the exact Device ID you are testing in your browser
    test_id = "50400" 
    
    print(f"🔎 STARTING BACKEND DIAGNOSTIC FOR DEVICE ID: {test_id}")
    print("-" * 60)
    
    client = ONCClient()
    resolved_device_code = test_id
    
    # 1. Test Code Resolution Step
    if test_id.isdigit():
        try:
            res = client._onc.getDevices({"deviceId": int(test_id)})
            if isinstance(res, list) and len(res) > 0:
                resolved_device_code = res[0].get("deviceCode", test_id)
            elif isinstance(res, dict) and "devices" in res:
                resolved_device_code = res["devices"][0].get("deviceCode", test_id)
            print(f"🔹 Step 1: Resolved numeric ID '{test_id}' to Code: '{resolved_device_code}'")
        except Exception as e:
            print(f"❌ Step 1 Failure: Could not resolve ID via ONC API: {e}")
            return

    # 2. Test Device Category Fetch Step
    try:
        device = client.get_device(device_code=resolved_device_code)
        category_code = device.get("deviceCategoryCode", "")
        numeric_id = device.get("deviceId", "")
        
        print(f"🔹 Step 2: Retrieved ONC Device Category Code: '{category_code}'")
        print(f"🔹 Step 2: Retrieved ONC Database Device ID: '{numeric_id}'")
    except Exception as e:
        print(f"❌ Step 2 Failure: client.get_device() crashed: {e}")
        import traceback
        traceback.print_exc()
        return

    # 3. Test Conditional Mapping Step
    print(f"🔹 Step 3: Checking if '{category_code.upper()}' == 'HYDROPHONE'...")
    if category_code.upper() == "HYDROPHONE":
        print("   👉 MATCH CONFIRMED! Calling get_hydrophone_checklist_ui()...")
        try:
            html = get_hydrophone_checklist_ui(str(numeric_id))
            print(f"🔹 Step 4: UI function returned string length: {len(html or '')} characters.")
            if html and len(html.strip()) > 0:
                print("   ✅ SUCCESS: Checklist string generated flawlessly!")
                print("\n--- Snippet Preview ---")
                print(html.strip()[:250] + "...\n-----------------------")
            else:
                print("   ❌ FAILURE: UI function returned a blank or null string.")
        except Exception as e:
            print(f"   ❌ FAILURE: UI Function crashed internally: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"   ❌ FAILURE: Category is '{category_code.upper()}', NOT 'HYDROPHONE'.")
        print("   The backend logic skipped generating the checklist entirely.")

if __name__ == "__main__":
    run_diagnostic()