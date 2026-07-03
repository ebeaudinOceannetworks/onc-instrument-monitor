# tests/test_72h_build.py
import sys
from pathlib import Path

# Path bootstrap to locate the root core utilities folder
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from data_types.scalar_site.plugin import ScalarSitePlugin

def run_isolated_build_test():
    print("=" * 95)
    print("🔬 RUNNING ISOLATED 72-HOUR BACKEND PLUG-IN BUILD TEST")
    print("=" * 95)

    # Initialize the plugin with a small list of active scalar categories
    try:
        plugin = ScalarSitePlugin(categories=["CTD", "FLNTU", "OXYSENSOR"])
        plugin._lookback_hours = 72  # Force the 72-hour test ceiling target
    except Exception as e:
        print(f"❌ Failed to initialize ScalarSitePlugin: {e}")
        return

    print("🛰️ Connecting to ONC network to pull an active testing asset...")
    try:
        # Discover a live device to pipe into our build compiler method
        active_devices = plugin._client.discover_active_devices("CTD")
        if not active_devices:
            print("⚠️ No active CTD devices found. Trying FLNTU...")
            active_devices = plugin._client.discover_active_devices("FLNTU")
            
        if not active_devices:
            print("❌ Error: Could not find any active network devices to test against.")
            return
            
        target_device = active_devices[0]
        print(f"🎯 Target Found: {target_device.get('deviceCode')} (ID: {target_device.get('deviceId')})")
    except Exception as e:
        print(f"❌ Network Discovery Failed: {e}")
        return

    print(f"⏳ Executing _build_device() for a {plugin._lookback_hours}-hour window...")
    try:
        payload = plugin._build_device(target_device)
    except Exception as e:
        print(f"❌ Crashing inside _build_device(): {e}")
        import traceback
        traceback.print_exc()
        return

    # --- RESULTS DISCOVERY ANALYSIS ---
    print("\n" + "=" * 95)
    print("📊 ISOLATED BACKEND OUTPUT REPORT")
    print("=" * 95)
    print(f"Device Code:     {payload.get('deviceCode')}")
    print(f"Lookback Hours:  {payload.get('lookback_hours')}")
    
    clean_series = payload.get("plot_series", {}).get("clean", [])
    raw_series = payload.get("plot_series", {}).get("raw", [])
    
    print(f"Clean Data rows: {len(clean_series)}")
    print(f"Raw Data rows:   {len(raw_series)}")
    print("-" * 95)

    if len(clean_series) > 0:
        print("🟢 SUCCESS: Python is successfully capturing and formatting Clean data points!")
        print(f"   Sample Data point 1: {clean_series[0]}")
    else:
        print("❌ ERROR: Clean series data is completely empty inside Python.")

    if len(raw_series) > 0:
        print("🟢 SUCCESS: Python is successfully capturing and formatting Raw data points!")
        print(f"   Sample Data point 1: {raw_series[0]}")
    else:
        print("❌ ERROR: Raw series data is completely empty inside Python.")
        
    print("=" * 95)

if __name__ == "__main__":
    run_isolated_build_test()