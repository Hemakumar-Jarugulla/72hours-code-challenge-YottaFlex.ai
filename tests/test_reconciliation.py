"""
Unit Tests for Waterfall Payment Allocation & Commitment Reconciliation.
"""

import sqlite3
import pytest
from database.db import get_db_connection, init_database
from engine.ptp_reconciliation_engine import allocate_payment_waterfall, evaluate_overdue_ptps


@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    
    with open("database/schema.sql", "r", encoding="utf-8") as f:
        conn.executescript(f.read())
        
    # Seed baseline customer, account, loan, installments, case
    conn.execute("""
        INSERT INTO customers VALUES (
            'CUST-T01', 'Test', 'Borrower', 'test@example.com', '+15551234567',
            'America/New_York', 'MEDIUM', 'NONE', 'NONE', 0, 0, '2026-01-01T00:00:00Z'
        )
    """)
    conn.execute("""
        INSERT INTO accounts VALUES (
            'ACC-T01', 'CUST-T01', '1234567890', 'OPEN', 5000.0, '2026-01-05'
        )
    """)
    conn.execute("""
        INSERT INTO loans VALUES (
            'LOAN-2026-T01', 'ACC-T01', 'CUST-T01', 'PERSONAL', 1000.0, 0.10, 12,
            '2026-01-10', '2027-01-10', 300.0, 600.0, 600.0, 60, 'DELINQUENT'
        )
    """)
    conn.execute("""
        INSERT INTO installments VALUES (
            'INS-LOAN-2026-T01-001', 'LOAN-2026-T01', 1, '2026-02-10',
            280.0, 20.0, 300.0, 0.0, 300.0, 60, 'OVERDUE'
        )
    """)
    conn.execute("""
        INSERT INTO installments VALUES (
            'INS-LOAN-2026-T01-002', 'LOAN-2026-T01', 2, '2026-03-10',
            280.0, 20.0, 300.0, 0.0, 300.0, 30, 'OVERDUE'
        )
    """)
    conn.execute("""
        INSERT INTO collection_cases VALUES (
            'COL-2026-T01', 'LOAN-2026-T01', 'CUST-T01', '2026-02-15',
            'ACTIVE', 65.0, 'P2_HIGH', 'AGENT-001', NULL, NULL, NULL, 0, 0
        )
    """)
    conn.commit()
    yield conn
    conn.close()


def test_waterfall_allocation_chronological_order(test_db):
    # Payment of $400: should fully satisfy installment #1 ($300), and $100 applied to installment #2
    res = allocate_payment_waterfall(
        test_db,
        loan_id="LOAN-2026-T01",
        payment_amount=400.0,
        payment_date="2026-04-01",
        payment_method="ACH"
    )

    assert res["amount"] == 400.0
    assert len(res["allocations"]) == 2
    assert res["allocations"][0]["installment_id"] == "INS-LOAN-2026-T01-001"
    assert res["allocations"][0]["allocated_amount"] == 300.0
    assert res["allocations"][0]["status"] == "PAID"

    assert res["allocations"][1]["installment_id"] == "INS-LOAN-2026-T01-002"
    assert res["allocations"][1]["allocated_amount"] == 100.0
    assert res["allocations"][1]["remaining_balance"] == 200.0
    assert res["allocations"][1]["status"] == "PARTIALLY_PAID"

    # Loan remaining balance should now be $200
    assert res["new_balance"] == 200.0
    assert res["new_arrears"] == 200.0


def test_waterfall_full_payoff_closes_case(test_db):
    # Payment of remaining $600: fully pays off loan and auto-closes collection case
    res = allocate_payment_waterfall(
        test_db,
        loan_id="LOAN-2026-T01",
        payment_amount=600.0,
        payment_date="2026-04-01"
    )

    assert res["loan_status"] == "PAID_OFF"
    assert res["new_balance"] == 0.0
    assert res["new_arrears"] == 0.0
    assert res["case_status"] == "CLOSED_PAID"

    case = test_db.execute("SELECT * FROM collection_cases WHERE case_id = 'COL-2026-T01'").fetchone()
    assert case["case_status"] == "CLOSED_PAID"
    assert case["priority_score"] == 0.0


def test_ptp_reconciliation_kept(test_db):
    # Insert active PTP for $300
    test_db.execute("""
        INSERT INTO promises_to_pay VALUES (
            'PTP-2026-T01', 'COL-2026-T01', 'LOAN-2026-T01', 'CUST-T01',
            '2026-03-25T10:00:00Z', '2026-04-05', 300.0, 600.0, 'PENDING', 0.0, NULL, NULL
        )
    """)
    test_db.commit()

    # Customer pays $300 on 2026-04-02
    res = allocate_payment_waterfall(
        test_db,
        loan_id="LOAN-2026-T01",
        payment_amount=300.0,
        payment_date="2026-04-02",
        ptp_id="PTP-2026-T01"
    )

    assert res["ptp_reconciliation"]["status"] == "KEPT"
    assert res["ptp_reconciliation"]["fulfilled_amount"] == 300.0


def test_ptp_expiration_broken(test_db):
    # Insert expired PTP
    test_db.execute("""
        INSERT INTO promises_to_pay VALUES (
            'PTP-2026-T02', 'COL-2026-T01', 'LOAN-2026-T01', 'CUST-T01',
            '2026-03-01T10:00:00Z', '2026-03-10', 300.0, 600.0, 'PENDING', 0.0, NULL, NULL
        )
    """)
    test_db.commit()

    # Reference date is 2026-03-15 (> 1 day past due date 2026-03-10)
    broken = evaluate_overdue_ptps(test_db, reference_date="2026-03-15")
    assert len(broken) == 1
    assert broken[0]["new_status"] == "BROKEN"

    ptp = test_db.execute("SELECT * FROM promises_to_pay WHERE ptp_id = 'PTP-2026-T02'").fetchone()
    assert ptp["ptp_status"] == "BROKEN"
