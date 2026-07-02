# tests/inspect_data_columns.py
import sys
from pathlib import Path

# Path bootstrap to locate the core utilities folder
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.db import get_db_connection

conn = get_db_connection()
if conn:
    try:
        with conn.cursor() as cur:
            # We will look up the column definitions for our top two candidates
            target_tables = ("scalardata_30", "quarterscalardata")
            
            for table in target_tables:
                cur.execute(f"""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = '{table}';
                """)
                columns = cur.fetchall()
                
                print(f"\n📊 COLUMNS FOR TABLE: {table}")
                print("-" * 50)
                if columns:
                    for col_name, data_type in columns:
                        print(f" - {col_name:<25} ({data_type})")
                else:
                    print(" (No columns found or table is a view without direct schema listings)")
                print("-" * 50)
    except Exception as e:
        print(f"Error executing column check: {e}")
    finally:
        conn.close()
else:
    print("❌ Could not establish database connection.")