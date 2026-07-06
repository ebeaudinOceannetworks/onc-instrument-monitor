# tests/test_hydrophone_analysis.py
import sys
import os
from pathlib import Path

# Bootstrap the path environment to locate root directory utilities
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from workflows.commissioning import CommissioningRequest, run_commissioning

def run_pipeline_integrity_test():
    print("=" * 95)
    print("🔬 RUNNING LIVE HYDROPHONE ANALYSIS & PLOT GENERATION INTEGRITY TEST")
    print("=" * 95)

    request = CommissioningRequest(
        device_code="ICLISTENHF6021",
        location_code="KVIP",
        deployment="2025-09-10|active|KVIP", # Exact historical target deployment window
        review_phase="detailed"
    )

    print("⏳ Executing commissioning pipeline (downloading assets & compiling datasets)...")
    result = run_commissioning(request=request)
    
    print(f"\n🟢 Pipeline Execution Complete. Status: {result.get('status')}")
    
    # Verify file presence on disk
    target_plots_dir = "public/static/generated_plots/KVIP_ICLISTENHF6021"
    
    print(f"\n📁 Auditing target web asset directory: '{target_plots_dir}'")
    
    expected_files = [
        "data_completeness.png",
        "ambient_noise.png"
    ]
    
    all_passed = True
    for plot_file in expected_files:
        full_path = os.path.join(target_plots_dir, plot_file)
        print(f"   -> Checking '{plot_file}':")
        if os.path.exists(full_path):
            file_size_kb = os.path.getsize(full_path) / 1024
            print(f"      ✅ FOUND! File size: {file_size_kb:.2f} KB")
        else:
            print(f"      ❌ MISSING! The image asset failed to render to disk.")
            all_passed = False

    plots_array = result.get("plots", [])
    print(f"\n📦 Output Payload Verification:")
    print(f"   -> Frontend plots array count: {len(plots_array)}")
    
    if all_passed and len(plots_array) == 2:
        print("\n🟢 TEST CONCLUSION: SUCCESS! The data pipeline is fully operational.")
    else:
        print("\n❌ TEST CONCLUSION: FAILURE. Review the missing components or empty data logs above.")
    print("=" * 95)

if __name__ == "__main__":
    run_pipeline_integrity_test()