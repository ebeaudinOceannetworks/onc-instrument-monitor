# tests/inspect_raw_and_instrument.py
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.db import get_db_connection

DEVICE_ID = 23843
JB_SENSOR_IDS = (4944, 4949, 5811, 5816)

def run_deep_check():
    conn = get_db_connection()
    if not conn:
        print("❌ Could not connect to the database.")
        return

    try:
        with conn.cursor() as cur:
            print("=" * 70)
            print("🔍 PHASE 1: CHECKING PRIMARY INSTRUMENT (CTD) IN SCALAR DATA")
            print("=" * 70)
            
            # FIXED: Changed sn.sensortype_name back to sn.sensortypename
            cur.execute("""
                SELECT s.sensorid, sc.sensorcode, sn.sensortypename
                FROM sensor s
                JOIN sensorcode sc ON sc.sensorcodeid = s.sensorcodeid
                LEFT JOIN sensortype sn ON sn.sensortypeid = s.sensortypeid
                WHERE s.deviceid = %s
                LIMIT 5;
            """, (DEVICE_ID,))
            ctd_sensors = cur.fetchall()
            
            if ctd_sensors:
                for s_id, s_code, s_type in ctd_sensors:
                    cur.execute("SELECT COUNT(*) FROM scalardata_30 WHERE sensorid = %s", (s_id,))
                    count = cur.fetchone()[0]
                    print(f" -> CTD Sensor {s_id} ({s_code} - {s_type or 'Unknown'}): {count} rows in scalardata_30")
            else:
                print(" ⚠️ No direct sensors found for the primary device ID in the metadata registry.")

            print("\n" + "=" * 70)
            print("🔍 PHASE 2: SEARCHING RAW BUFFER TABLES FOR JUNCTION BOX CHANNELS")
            print("=" * 70)
            
            # Inspect the columns of rawdataeven to see if it routes by sensorid or deviceid
            cur.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'rawdataeven' AND column_name IN ('sensorid', 'deviceid');
            """)
            raw_columns = [row[0] for row in cur.fetchall()]
            print(f"Detected columns in raw buffer tables: {raw_columns}")
            
            if not raw_columns:
                print(" ❌ Raw data tables do not expose explicit sensorid/deviceid routing keys.")
                return
                
            routing_col = raw_columns[0]
            
            for table in ("rawdataeven", "rawdataodd"):
                print(f"\nScanning {table}:")
                for s_id in JB_SENSOR_IDS:
                    cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {routing_col} = %s", (s_id,))
                    count = cur.fetchone()[0]
                    print(f"   - Sensor {s_id}: {count} raw telemetry packets found.")

    except Exception as e:
        print(f"❌ Structural check failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run_deep_check()