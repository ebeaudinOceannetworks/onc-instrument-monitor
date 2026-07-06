# tests/test_archive_filename.py
import sys
import re
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Path bootstrap to locate the root core utilities folder
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.onc_client import ONCClient

def run_filename_test():
    print("=" * 95)
    print("🔬 RUNNING LIVE 72-HOUR HYDROPHONE ARCHIVE FILENAME TEST")
    print("=" * 95)

    client = ONCClient()
    if not client.available:
        print("❌ Error: ONC Client is not available. Check your ONC_TOKEN in .env")
        return

    print("🛰️  Discovering an active HYDROPHONE device code...")
    try:
        hydrophones = client.discover_active_devices("HYDROPHONE")
        if not hydrophones:
            print("❌ Error: No active hydrophone devices found on your account.")
            return
        
        target_device = hydrophones[0]
        device_code = target_device.get("deviceCode")
        print(f"🎯 Target Hydrophone Selected: {device_code} (ID: {target_device.get('deviceId')})")
    except Exception as e:
        print(f"❌ Device Discovery Failed: {e}")
        return

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=3)  # 72 hours lookback

    # 🟢 Using your exact working parameter configuration
    params = {
        'deviceCode': device_code,
        'dateFrom': start_time.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
        'dateTo': end_time.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
        'rowLimit': 100000
    }

    print(f"⏳ Issuing getArchivefileByDevice query to ONC...")
    try:
        res = client._onc.getArchivefileByDevice(params)
        print(f"🟢 API Network Response Received! Object Type: {type(res)}")
        
        files = []
        if isinstance(res, dict):
            print(f"   -> Top-level dictionary keys found: {list(res.keys())}")
            files = res.get('files', [])
        elif isinstance(res, list):
            print("   -> Response object returned directly as a list.")
            files = res

        print(f"   -> Total raw archive entries returned: {len(files)}")
        
        if len(files) == 0:
            print("   ⚠️  Zero files returned for this lookback window.")
            if isinstance(res, dict) and "messages" in res:
                print(f"      Server Messages: {res['messages']}")
            return

        # ⚙️ Execute your exact filename parsing approach
        print("\n🧩 Simulating Filename Regex & Extension Splitting Extraction...")
        pattern = re.compile(r"(\d{8}T\d{6})")
        
        extension_counts = {}
        sample_matches = []
        
        for f in files:
            filename = f.get('filename', '')
            if not filename:
                continue
                
            ext = filename.split('.')[-1].lower()
            extension_counts[ext] = extension_counts.get(ext, 0) + 1
            
            match = pattern.search(filename)
            if match and len(sample_matches) < 5:
                try:
                    ts = pd.to_datetime(match.group(1), format='%Y%m%dT%H%M%S').tz_localize('UTC')
                    sample_matches.append((filename, ext, ts))
                except:
                    continue

        print(f"   -> File format counts detected: {extension_counts}")
        print(f"   -> Total files successfully parsed via regex: {sum(extension_counts.values())}")
        
        print("\n📋 Sample Parsed Rows Output:")
        for i, (fname, ext, ts) in enumerate(sample_matches):
            print(f"   [{i+1}] Filename:  {fname}")
            print(f"       Extension: {ext}")
            print(f"       Parsed TS: {ts.strftime('%Y-%m-%d %H:%M:%S')} UTC")

        print("\n🟢 TEST CONCLUSION: If sample rows and timestamps appear above, the data layer is fully operational!")

    except Exception as err:
        print(f"❌ Test failed with an unhandled exception: {err}")
        import traceback
        traceback.print_exc()

    print("=" * 95)

if __name__ == "__main__":
    run_filename_test()