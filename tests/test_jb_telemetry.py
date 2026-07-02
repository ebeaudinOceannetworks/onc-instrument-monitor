# tests/test_jb_telemetry.py
import sys
from pathlib import Path

# Path bootstrap to locate the root core utilities folder
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.db import get_db_connection

# Target device from your screenshot
TARGET_DEVICE_ID = 23843

def run_diagnostic():
    conn = get_db_connection()
    if not conn:
        print("❌ Could not connect to the database.")
        return

    try:
        with conn.cursor() as cur:
            # 1. First, let's find the exact connected sensors via the topology walk
            print("=" * 70)
            print(f"📡 SCANNING TOPOLOGY SENSORS FOR DEVICE: {TARGET_DEVICE_ID}")
            print("=" * 70)
            
            topology_query = """
            WITH RECURSIVE topology_device(deviceid, devicecode, devicecategoryid, deviceportid) AS (
                SELECT d.deviceid, d.devicecode, d.devicecategoryid, dp1.deviceportid
                FROM device d
                JOIN deviceport dp2 ON dp2.deviceid = d.deviceid
                JOIN topology t1 ON t1.deviceportid2 = dp2.deviceportid
                JOIN deviceport dp1 ON dp1.deviceportid = t1.deviceportid1
                WHERE d.deviceid = %s
                UNION
                SELECT d.deviceid, d.devicecode, d.devicecategoryid, dp1.deviceportid
                FROM topology_device td
                JOIN deviceport dp2 ON dp2.deviceid = td.deviceid
                JOIN topology t1 ON t1.deviceportid2 = dp2.deviceportid
                JOIN deviceport dp1 ON dp1.deviceportid = t1.deviceportid1
                JOIN device d ON d.deviceid = dp1.deviceid
                WHERE t1.dateto IS NULL
            )
            SELECT DISTINCT s.sensorid, td.devicecode, sc.sensorcode
            FROM topology_device td
            JOIN sensor s ON s.deviceportid = td.deviceportid
            JOIN sensorcode sc ON sc.sensorcodeid = s.sensorcodeid
            WHERE td.devicecategoryid = 38
            AND (sc.sensorcode LIKE '%%_status' OR sc.sensorcode LIKE '%%_voltagevalue');
            """
            
            cur.execute(topology_query, (TARGET_DEVICE_ID,))
            sensors = cur.fetchall()
            
            if not sensors:
                print("❌ No matching Junction Box status/voltage sensors found in topology walk!")
                return
                
            print(f"Found {len(sensors)} connected sensor channels. Querying raw tables...")
            
            # 2. For each sensor, look at the literal contents of the data tables
            for sensor_id, jb_code, sensor_code in sensors:
                print("\n" + "-" * 70)
                print(f"📊 SENSOR ID: {sensor_id} | JB: {jb_code} | CHANNEL: {sensor_code}")
                print("-" * 70)
                
                for table in ("scalardata_30", "quarterscalardata"):
                    cur.execute(f"""
                        SELECT COUNT(*), MAX(sampletime), AVG(cleanaverage), MIN(cleanaverage), MAX(cleanaverage)
                        FROM {table}
                        WHERE sensorid = %s
                    """, (sensor_id,))
                    count, max_time, avg_val, min_val, max_val = cur.fetchone()
                    
                    print(f" [{table}]:")
                    print(f"   - Total Data Rows:    {count}")
                    if count > 0:
                        print(f"   - Latest Timestamp:   {max_time}")
                        print(f"   - Value Range:        Min={min_val} | Max={max_val} | Avg={avg_val}")
                        
                        # Let's pull the absolute 3 most recent entries to see the changes
                        cur.execute(f"""
                            SELECT sampletime, cleanaverage, rawmin, rawmax, valid 
                            FROM {table} 
                            WHERE sensorid = %s 
                            ORDER BY sampletime DESC 
                            LIMIT 3
                        """, (sensor_id,))
                        print("   - Latest 3 Raw Entries:")
                        for stime, clean_avg, rmin, rmax, is_valid in cur.fetchall():
                            print(f"      * {stime} -> cleanaverage={clean_avg} (raw_range: {rmin} to {rmax}) [valid={is_valid}]")
                    else:
                        print("   - No rows found.")
                        
    except Exception as e:
        print(f"❌ Diagnostic failed with error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    run_diagnostic()