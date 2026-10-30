"""
Unit Tests for Detection and Remediation of the 5 Required Negative Scenarios:
1. Paid account remains in collection
2. Contact outside allowed window
3. Payment allocated to wrong installment
4. Promise amount exceeds arrears
5. Disputed debt treated as confirmed
"""

import sqlite3
import pytest
from database.db import get_db_connection, init_database
from generator.synthetic_generator import SyntheticDataGenerator
from engine.anomaly_detector import scan_anomalies, remediate_anomaly


@pytest.fixture(scope="module")
def populated_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    with open("database/schema.sql", "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    # Generate starter dataset with injected edge cases
    gen = SyntheticDataGenerator(seed=20261022, profile_name="starter")
    gen.generate_all()
    gen.export_to_sqlite(conn)

    yield conn
    conn.close()


def test_anomaly_scan_detects_all_five_scenarios(populated_db):
    anomalies = scan_anomalies(populated_db)
    detected_types = {a["issue_type"] for a in anomalies}

    assert "PAID_ACCOUNT_REMAINS_IN_COLLECTION" in detected_types
    assert "CONTACT_OUTSIDE_ALLOWED_WINDOW" in detected_types
    assert "PAYMENT_ALLOCATED_TO_WRONG_INSTALLMENT" in detected_types
    assert "PROMISE_AMOUNT_EXCEEDS_ARREARS" in detected_types
    assert "DISPUTED_DEBT_TREATED_AS_CONFIRMED" in detected_types


def test_remediate_paid_account_remains_in_collection(populated_db):
    anomalies = scan_anomalies(populated_db)
    paid_scen = next((a for a in anomalies if a["issue_type"] == "PAID_ACCOUNT_REMAINS_IN_COLLECTION"), None)
    assert paid_scen is not None

    res = remediate_anomaly(populated_db, paid_scen)
    assert res["status"] == "SUCCESS"

    case = populated_db.execute(
        "SELECT case_status FROM collection_cases WHERE case_id = ?",
        (paid_scen["entity_id"],)
    ).fetchone()
    assert case["case_status"] == "CLOSED_PAID"


def test_remediate_contact_outside_window(populated_db):
    anomalies = scan_anomalies(populated_db)
    quiet_scen = next((a for a in anomalies if a["issue_type"] == "CONTACT_OUTSIDE_ALLOWED_WINDOW"), None)
    assert quiet_scen is not None

    res = remediate_anomaly(populated_db, quiet_scen)
    assert res["status"] == "SUCCESS"

    att = populated_db.execute(
        "SELECT compliance_status FROM contact_attempts WHERE attempt_id = ?",
        (quiet_scen["entity_id"],)
    ).fetchone()
    assert att["compliance_status"] == "QUIET_HOURS_VIOLATION"


def test_remediate_promise_exceeds_arrears(populated_db):
    anomalies = scan_anomalies(populated_db)
    ptp_scen = next((a for a in anomalies if a["issue_type"] == "PROMISE_AMOUNT_EXCEEDS_ARREARS"), None)
    assert ptp_scen is not None

    res = remediate_anomaly(populated_db, ptp_scen)
    assert res["status"] == "SUCCESS"

    ptp = populated_db.execute(
        "SELECT promised_amount, current_arrears_at_promise FROM promises_to_pay WHERE ptp_id = ?",
        (ptp_scen["entity_id"],)
    ).fetchone()
    assert ptp["promised_amount"] == ptp["current_arrears_at_promise"]
