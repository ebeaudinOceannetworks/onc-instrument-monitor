"""PostgreSQL helpers and junction-box status lookup."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

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
    """
    sql_path = SQL_DIR / "jb_status.sql"
    if not sql_path.exists():
        return []

    conn = get_db_connection()
    if conn is None:
        return []

    query = sql_path.read_text(encoding="utf-8")
    rows: list[dict[str, Any]] = []
    try:
        with conn.cursor() as cur:
            cur.execute(query, (int(device_id),))
            columns = [desc[0] for desc in cur.description]
            for record in cur.fetchall():
                rows.append(dict(zip(columns, record)))
    finally:
        conn.close()
    return rows
