"""PostgreSQL helpers and junction-box status lookup."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
import time
import psycopg2

from dotenv import load_dotenv

load_dotenv()

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def db_configured() -> bool:
    return all(
        os.getenv(var) for var in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
    )


def get_db_connection():
    import psycopg2

    db_host = os.getenv("DB_HOST")
    db_name = os.getenv("DB_NAME")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    if not all([db_host, db_name, db_user, db_password]):
        return None
    return psycopg2.connect(
        host=db_host,
        dbname=db_name,
        user=db_user,
        password=db_password,
    )


def get_jb_info_for_device(device_id: int | str) -> list[dict[str, Any]]:
    """Return junction-box voltage sensor info connected to a device.

    Uses sql/jb_status.sql from the DAQ-dashboard folder (topology walk).
    Resilient against Hot Standby replica serialization recovery conflicts.
    """
    sql_path = SQL_DIR / "jb_status.sql"
    if not sql_path.exists():
        return []

    query = sql_path.read_text(encoding="utf-8")
    
    MAX_RETRIES = 3
    BACKOFF_DELAY = 0.5  # Base seconds to sleep between attempts

    for attempt in range(1, MAX_RETRIES + 1):
        conn = get_db_connection()
        if conn is None:
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFF_DELAY)
                continue
            return []

        try:
            # Tell the read-only standby node we don't need transactional row locks
            conn.set_session(readonly=True, autocommit=True)
            
            with conn.cursor() as cur:
                cur.execute(query, (int(device_id),))
                columns = [desc[0] for desc in cur.description]
                
                rows: list[dict[str, Any]] = []
                for record in cur.fetchall():
                    rows.append(dict(zip(columns, record)))
                
                # Success! Return the data immediately
                return rows

        except Exception as e:
            err_str = str(e).lower()
            # Intercept standard replication blips or serialization failure codes
            if ("conflict with recovery" in err_str or "serialization" in err_str) and attempt < MAX_RETRIES:
                print(f"🔄 Standby replica conflict on device {device_id}. Retrying attempt {attempt}/{MAX_RETRIES}...")
                time.sleep(BACKOFF_DELAY * attempt)  # Incremental backoff delay
                continue
            
            # If it's a real issue or we're out of retries, log it and bubble up the exception
            print(f"❌ Database execution failure on device {device_id}: {e}")
            raise e
            
        finally:
            # Always close the connection instance for this attempt block before looping or returning
            conn.close()

    return []

def get_monitored_junction_boxes() -> list[dict[str, Any]]:
    """Return all junction box device IDs matching criteria in data_request.sql.
    
    This helps discover which devices should be loaded onto the dashboard.
    """
    sql_path = SQL_DIR / "data_request.sql"
    if not sql_path.exists():
        return []

    conn = get_db_connection()
    if conn is None:
        return []

    query = sql_path.read_text(encoding="utf-8")
    rows: list[dict[str, Any]] = []
    try:
        with conn.cursor() as cur:
            # This query doesn't require any parameters (%s)
            cur.execute(query)
            columns = [desc[0] for desc in cur.description]
            for record in cur.fetchall():
                rows.append(dict(zip(columns, record)))
    finally:
        conn.close()
    return rows