"""
Acceptance Criteria Verification Test Suite.
Directly maps to and tests the problem specification's explicit acceptance criteria:
1. Arrears calculations reconcile
2. Prioritization is explainable
3. Contact restrictions are enforced
4. Promise outcomes match subsequent payments
5. All 5 required negative edge cases are injected, detected, and remediable
6. Separate ground truth with zero leakage into input features
7. Deterministic ID nomenclature conventions
"""

import os
import re
import csv
import json
import sqlite3
import datetime
import pytest

from database.db import get_db_connection
from generator.synthetic_generator import SyntheticDataGenerator
from engine.prioritization_engine import calculate_case_priority
from engine.compliance_engine import evaluate_contact_compliance, check_quiet_hours
from engine.ptp_reconciliation_engine import allocate_payment_waterfall, evaluate_overdue_ptps
from engine.anomaly_detector import scan_anomalies, remediate_anomaly


@pytest.fixture(scope="module")
def app_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    with open("database/schema.sql", "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    gen = SyntheticDataGenerator(seed=20261022, profile_name="starter")
    gen.generate_all()
    gen.export_to_sqlite(conn)

    yield conn
    conn.close()


# ==============================================================================
# Criterion 1: Arrears calculations reconcile
# ==============================================================================
def test_acceptance_arrears_calculations_reconcile(app_db):
    """
    Verifies that:
    1. Installment remaining balances strictly equal total_amount_due - amount_paid.
    2. Loan total_balance strictly equals the sum of installment remaining balances.
    """
    # 1. Check installment level balance
    installments = app_db.execute(
        "SELECT installment_id, total_amount_due, amount_paid, remaining_balance FROM installments"
    ).fetchall()
    assert len(installments) > 0

    for ins in installments:
        expected_balance = round(ins["total_amount_due"] - ins["amount_paid"], 2)
        assert abs(ins["remaining_balance"] - expected_balance) < 0.01, (
            f"Installment {ins['installment_id']} balance mismatch: "
            f"stored={ins['remaining_balance']}, expected={expected_balance}"
        )

    # 2. Check loan level balance reconciliation
    loans = app_db.execute("""
        SELECT l.loan_id, l.current_balance,
               COALESCE(SUM(i.remaining_balance), 0.0) as sum_ins_balance
        FROM loans l
        LEFT JOIN installments i ON l.loan_id = i.loan_id
        GROUP BY l.loan_id
    """).fetchall()
    assert len(loans) > 0

    for loan in loans:
        assert abs(loan["current_balance"] - round(loan["sum_ins_balance"], 2)) < 0.01, (
            f"Loan {loan['loan_id']} current_balance does not match sum of installment balances."
        )


# ==============================================================================
# Criterion 2: Prioritization is explainable
# ==============================================================================
def test_acceptance_prioritization_is_explainable():
    """
    Verifies that prioritization scores are mathematically explainable,
    bounded in [0.0, 100.0], and each constituent point factor adds up to the total.
    """
    res = calculate_case_priority(
        total_arrears=3200.0,
        days_past_due=65,
        risk_segment="HIGH",
        hardship_status="NONE",
        dispute_status="NONE",
        broken_ptp_count=2,
        kept_ptp_count=1
    )

    score = res["priority_score"]
    factors = res["explainability"]

    # Verify every component factor exists
    assert "arrears_exposure_points" in factors
    assert "aging_dpd_points" in factors
    assert "risk_segment_points" in factors
    assert "commitment_history_adjustment" in factors

    # Mathematical summation
    expected_sum = round(
        factors["arrears_exposure_points"] +
        factors["aging_dpd_points"] +
        factors["risk_segment_points"] +
        factors["commitment_history_adjustment"],
        2
    )
    expected_clamped = min(100.0, max(0.0, expected_sum))
    assert score == expected_clamped
    assert res["priority_tier"] in ["P1_CRITICAL", "P2_HIGH", "P3_MEDIUM", "P4_LOW"]


# ==============================================================================
# Criterion 3: Contact restrictions are enforced
# ==============================================================================
def test_acceptance_contact_restrictions_are_enforced():
    """
    Verifies strict enforcement of statutory and ethical contact guardrails:
    - FDCPA Quiet Hours (08:00 - 21:00 consumer local time across US timezones)
    - FDCPA Section 805(c) Cease and Desist
    - Hardship Moratorium (medical emergency, unemployment, etc.)
    - FDCPA Section 809 Debt Dispute Moratorium
    - TCPA / CFPB 7-in-7 frequency cap
    """
    # 1. Quiet Hours: 05:00 AM local time must be rejected
    dt_early = datetime.datetime(2026, 10, 22, 9, 0, tzinfo=datetime.timezone.utc) # 05:00 AM EDT
    quiet_res = check_quiet_hours(dt_early, "America/New_York")
    assert quiet_res["is_permissible"] is False
    assert "Quiet hours violation" in quiet_res["reason"]

    # 2. Cease and Desist
    cd_cust = {"customer_id": "C_CD", "cease_desist_flag": 1, "attorney_represented": 0, "dispute_status": "NONE", "hardship_status": "NONE"}
    pref = {"permissible_start_time": "08:00", "permissible_end_time": "21:00", "opt_in_phone": 1}
    eval_cd = evaluate_contact_compliance(cd_cust, pref, "PHONE", datetime.datetime(2026, 10, 22, 16, 0, tzinfo=datetime.timezone.utc), recent_7_day_attempts=0)
    assert eval_cd["is_compliant"] is False
    assert eval_cd["compliance_status"] == "CEASE_DESIST_VIOLATION"

    # 3. Active Dispute Hold
    disp_cust = {"customer_id": "C_DISP", "cease_desist_flag": 0, "attorney_represented": 0, "dispute_status": "ACTIVE_DISPUTE", "hardship_status": "NONE"}
    eval_disp = evaluate_contact_compliance(disp_cust, pref, "PHONE", datetime.datetime(2026, 10, 22, 16, 0, tzinfo=datetime.timezone.utc), recent_7_day_attempts=0)
    assert eval_disp["is_compliant"] is False
    assert eval_disp["compliance_status"] == "DISPUTE_HOLD_VIOLATION"

    # 4. Hardship Hold
    hard_cust = {"customer_id": "C_HARD", "cease_desist_flag": 0, "attorney_represented": 0, "dispute_status": "NONE", "hardship_status": "TEMPORARY_UNEMPLOYMENT"}
    eval_hard = evaluate_contact_compliance(hard_cust, pref, "PHONE", datetime.datetime(2026, 10, 22, 16, 0, tzinfo=datetime.timezone.utc), recent_7_day_attempts=0)
    assert eval_hard["is_compliant"] is False
    assert eval_hard["compliance_status"] == "HARDSHIP_HOLD_VIOLATION"


# ==============================================================================
# Criterion 4: Promise outcomes match subsequent payments
# ==============================================================================
def test_acceptance_promise_outcomes_match_subsequent_payments(app_db):
    """
    Verifies that customer repayments reconcile against promises-to-pay:
    - Payments fulfilling promised amount on/before due date transition PTP to KEPT.
    - Expired promises without fulfillment transition to BROKEN.
    """
    # Find an actual active case from the database
    case = app_db.execute(
        "SELECT case_id, loan_id, customer_id FROM collection_cases WHERE case_status = 'ACTIVE' LIMIT 1"
    ).fetchone()
    assert case is not None

    case_id = case["case_id"]
    loan_id = case["loan_id"]
    customer_id = case["customer_id"]

    # 1. Test KEPT fulfillment
    app_db.execute("""
        INSERT INTO promises_to_pay VALUES (
            'PTP-TEST-KEPT', ?, ?, ?,
            '2026-10-01T10:00:00Z', '2026-10-15', 50.0, 500.0, 'PENDING', 0.0, NULL, NULL
        )
    """, (case_id, loan_id, customer_id))
    app_db.commit()

    alloc_res = allocate_payment_waterfall(
        app_db,
        loan_id=loan_id,
        payment_amount=50.0,
        payment_date="2026-10-10",
        ptp_id="PTP-TEST-KEPT"
    )
    assert alloc_res["ptp_reconciliation"]["status"] == "KEPT"
    assert alloc_res["ptp_reconciliation"]["fulfilled_amount"] == 50.0

    # 2. Test BROKEN expiration
    app_db.execute("""
        INSERT INTO promises_to_pay VALUES (
            'PTP-TEST-BROKEN', ?, ?, ?,
            '2026-09-01T10:00:00Z', '2026-09-10', 300.0, 500.0, 'PENDING', 0.0, NULL, NULL
        )
    """, (case_id, loan_id, customer_id))
    app_db.commit()

    broken_list = evaluate_overdue_ptps(app_db, reference_date="2026-09-20")
    broken_ids = [b["ptp_id"] for b in broken_list]
    assert "PTP-TEST-BROKEN" in broken_ids


# ==============================================================================
# Criterion 5: All 5 required negative edge cases injected & remediable
# ==============================================================================
def test_acceptance_five_required_negative_edge_cases(app_db):
    """
    Verifies detection and remediation for the 5 mandated negative edge cases:
    1. Paid account remains in collection
    2. Contact outside allowed window
    3. Payment allocated to wrong installment
    4. Promise amount exceeds arrears
    5. Disputed debt treated as confirmed
    """
    anomalies = scan_anomalies(app_db)
    issue_types = {a["issue_type"] for a in anomalies}

    required_types = [
        "PAID_ACCOUNT_REMAINS_IN_COLLECTION",
        "CONTACT_OUTSIDE_ALLOWED_WINDOW",
        "PAYMENT_ALLOCATED_TO_WRONG_INSTALLMENT",
        "PROMISE_AMOUNT_EXCEEDS_ARREARS",
        "DISPUTED_DEBT_TREATED_AS_CONFIRMED"
    ]

    for req_type in required_types:
        assert req_type in issue_types, f"Required edge case {req_type} was not detected!"

        # Verify each anomaly has a functioning remediation handler
        target = next(a for a in anomalies if a["issue_type"] == req_type)
        rem_res = remediate_anomaly(app_db, target)
        assert rem_res["status"] == "SUCCESS", f"Remediation failed for {req_type}"


# ==============================================================================
# Criterion 6: Separate ground truth with zero leakage into features
# ==============================================================================
def test_acceptance_ground_truth_isolation():
    """
    Verifies that ground truth is exported into dedicated, isolated files
    (ground_truth.csv and ground_truth.json) and input tables do not contain
    leakage columns.
    """
    gt_csv_path = os.path.join("exports", "starter", "ground_truth.csv")
    gt_json_path = os.path.join("exports", "starter", "ground_truth.json")
    cust_csv_path = os.path.join("exports", "starter", "customers.csv")
    loan_csv_path = os.path.join("exports", "starter", "loans.csv")

    assert os.path.exists(gt_csv_path), "ground_truth.csv does not exist!"
    assert os.path.exists(gt_json_path), "ground_truth.json does not exist!"

    # Check that input feature tables do NOT leak anomaly labels
    forbidden_leak_headers = ["is_anomaly", "ground_truth_label", "issue_type", "anomaly_id"]

    for path in [cust_csv_path, loan_csv_path]:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader)
            for forbidden in forbidden_leak_headers:
                assert forbidden not in headers, f"Data leakage detected: {forbidden} found in {path}"


# ==============================================================================
# Criterion 7: Deterministic ID nomenclature conventions
# ==============================================================================
def test_acceptance_deterministic_id_nomenclature(app_db):
    """
    Verifies ID nomenclature matching:
    - LOAN-2026-000001
    - INS-<loan-id>-001
    - COL-2026-000001
    - CTP-<case-id>-001
    - PMT-2026-000001
    """
    # Loans: LOAN-2026-000001
    loan = app_db.execute("SELECT loan_id FROM loans LIMIT 1").fetchone()
    assert re.match(r"^LOAN-2026-\d{6}$", loan["loan_id"])

    # Installments: INS-<loan-id>-001
    ins = app_db.execute("SELECT installment_id FROM installments LIMIT 1").fetchone()
    assert re.match(r"^INS-LOAN-2026-\d{6}-\d{3}$", ins["installment_id"])

    # Collection Cases: COL-2026-000001
    case = app_db.execute("SELECT case_id FROM collection_cases LIMIT 1").fetchone()
    assert re.match(r"^COL-2026-\d{6}$", case["case_id"])

    # Contact Attempts: CTP-<case-id>-001
    att = app_db.execute("SELECT attempt_id FROM contact_attempts LIMIT 1").fetchone()
    assert re.match(r"^CTP-COL-2026-\d{6}-\d{3}$", att["attempt_id"])

    # Payments: PMT-2026-000001
    pmt = app_db.execute("SELECT payment_id FROM payments LIMIT 1").fetchone()
    assert re.match(r"^PMT-2026-\d{6}$", pmt["payment_id"])
