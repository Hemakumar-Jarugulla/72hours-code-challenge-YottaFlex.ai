"""
Database connection and management module for SQLite.
Enforces foreign keys, transaction safety, and provides connection utilities.
"""

import os
import sqlite3
from typing import Optional, List, Dict, Any

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "collections_engine.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Returns a SQLite connection with row_factory set to sqlite3.Row and PRAGMA foreign_keys enabled."""
    target_path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(target_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_database(db_path: Optional[str] = None, drop_existing: bool = False) -> None:
    """Initializes tables using schema.sql. If drop_existing is True, drops all existing tables first."""
    conn = get_db_connection(db_path)
    if drop_existing:
        tables = [
            "audit_events", "ground_truth_anomalies", "payments", "promises_to_pay",
            "contact_attempts", "collection_cases", "contact_preferences",
            "delinquency_snapshots", "installments", "loans", "accounts", "customers"
        ]
        with conn:
            conn.execute("PRAGMA foreign_keys = OFF;")
            for tbl in tables:
                conn.execute(f"DROP TABLE IF EXISTS {tbl};")
            conn.execute("PRAGMA foreign_keys = ON;")
            
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    with conn:
        conn.executescript(schema_sql)
    conn.close()


def log_audit_event(
    conn: sqlite3.Connection,
    entity_name: str,
    entity_id: str,
    action: str,
    actor_persona: str,
    actor_id: str,
    previous_state: Optional[str] = None,
    new_state: Optional[str] = None,
    notes: Optional[str] = None,
    event_timestamp: Optional[str] = None,
) -> None:
    """Logs an immutable event into audit_events for traceability."""
    import datetime
    ts = event_timestamp or datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO audit_events (
            event_timestamp, entity_name, entity_id, action,
            actor_persona, actor_id, previous_state, new_state, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ts, entity_name, entity_id, action, actor_persona, actor_id, previous_state, new_state, notes)
    )
