# tests/test_sensor_columns.py
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Now this will import perfectly from anywhere!
from core.db import get_db_connection

conn = get_db_connection()
if conn:
    try:
        with conn.cursor() as cur:
            # Look up the column names for the 'sensor' table
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'sensor';
            """)
            columns = [row[0] for row in cur.fetchall()]
            print("\n🔍 FOUND SENSOR TABLE COLUMNS:")
            print("-" * 40)
            for col in sorted(columns):
                print(f" - {col}")
            print("-" * 40)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
else:
    print("❌ Could not establish a database connection. Check your .env file!")