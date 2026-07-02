# tests/inspect_hydrophone_47240.py
import sys
from pathlib import Path

# Path bootstrap to locate 'core' from the tests directory
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.db import get_db_connection

HYDROPHONE_ID = 47240

def inspect_target_metadata():
    conn = get_db_connection()
    if not conn:
        print("❌ Could not connect to the database.")
        return

    print("=" * 90)
    print(f"🕵️ LOW-LEVEL TOPOLOGY INSPECTION FOR HYDROPHONE: {HYDROPHONE_ID}")
    print("=" * 90)

    try:
        with conn.cursor() as cur:
            # 1. Fetch the raw device details
            cur.execute("SELECT deviceid, devicecode, devicecategoryid FROM device WHERE deviceid = %s;", (HYDROPHONE_ID,))
            device = cur.fetchone()
            if not device:
                print(" ❌ BREAKPOINT: Device ID does not exist in the 'device' table.")
                return
            print(f" 🔹 Device Found: Code='{device[1]}' | CategoryID={device[2]}")

            # 2. Look for ports assigned to this device
            cur.execute("SELECT deviceportid, deviceportcode FROM deviceport WHERE deviceid = %s;", (HYDROPHONE_ID,))
            ports = cur.fetchall()
            print(f" 🔹 Device Ports: Found {len(ports)} rows.")
            for p_id, p_code in ports:
                print(f"    - Port ID: {p_id:<6} | Code/Label: '{p_code}'")

            if not ports:
                print(" ❌ BREAKPOINT: No ports found for this device. It cannot link to the topology tree.")
                return

            # 3. Pull any topology links where this device's ports appear on either side
            port_ids = [p[0] for p in ports]
            cur.execute("""
                SELECT t.topologyid, t.deviceportid1, t.deviceportid2, t.dateto,
                       d1.devicecode as dev1, d2.devicecode as dev2,
                       d1.devicecategoryid as cat1, d2.devicecategoryid as cat2
                FROM topology t
                JOIN deviceport dp1 ON dp1.deviceportid = t.deviceportid1
                JOIN device d1 ON d1.deviceid = dp1.deviceid
                JOIN deviceport dp2 ON dp2.deviceportid = t.deviceportid2
                JOIN device d2 ON d2.deviceid = dp2.deviceid
                WHERE t.deviceportid1 IN %s OR t.deviceportid2 IN %s;
            """, (tuple(port_ids), tuple(port_ids)))
            links = cur.fetchall()

            print(f" 🔹 Active/Historical Wiring Links: Found {len(links)} matching rows.")
            if not links:
                print("\n ❌ THE DIAGNOSIS: This instrument has 0 topology connections in the database.")
                print("    It is completely unlinked. The dash (—) on the dashboard is accurate because")
                print("    the database does not know what junction box this device is wired to.")
            else:
                for t_id, p1, p2, date_to, dev1, dev2, cat1, cat2 in links:
                    status = "🔴 CLOSED/HISTORICAL" if date_to else "🟢 LIVE/ACTIVE"
                    print(f"    - [Link #{t_id}] ({status})")
                    print(f"      Side 1: {dev1:<20} (Port ID: {p1}, Category: {cat1})")
                    print(f"      Side 2: {dev2:<20} (Port ID: {p2}, Category: {cat2})")

    except Exception as e:
        print(f" ❌ Inspection failed: {e}")
    finally:
        conn.close()
    print("=" * 90)

if __name__ == "__main__":
    inspect_target_metadata()