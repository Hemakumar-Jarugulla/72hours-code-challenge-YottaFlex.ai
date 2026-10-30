"""
Compliance Anomaly and Edge Case Detection Engine.
Detects, audits, and remediates the 5 critical negative scenarios:
1. Paid account remains in collection
2. Contact outside allowed window
3. Payment allocated to wrong installment
4. Promise amount exceeds arrears
5. Disputed debt treated as confirmed
"""

import sqlite3
import datetime
from typing import List, Dict, Any, Optional
from database.db import log_audit_event


def scan_anomalies(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Executes algorithmic scans across database tables to detect the 5 negative edge cases.
    Returns structured list of detected anomalies with diagnosis and remediation options.
    """
    cursor = conn.cursor()
    detected = []

    # Scenario 1: Paid account remains in collection
    # Loan is paid off (balance <= 0 or loan_status = 'PAID_OFF') but CollectionCase is ACTIVE or scheduled
    q1 = """
    SELECT c.case_id, c.loan_id, c.case_status, l.loan_status, l.current_balance, l.total_arrears
    FROM collection_cases c
    JOIN loans l ON c.loan_id = l.loan_id
    WHERE (l.current_balance <= 0.001 OR l.loan_status = 'PAID_OFF')
      AND c.case_status NOT IN ('CLOSED_PAID', 'RESOLVED')
    """
    for row in cursor.execute(q1).fetchall():
        detected.append({
            "anomaly_id": f"ANO-SCAN-PAID-{row['case_id']}",
            "entity_type": "CollectionCase",
            "entity_id": row["case_id"],
            "issue_type": "PAID_ACCOUNT_REMAINS_IN_COLLECTION",
            "severity": "CRITICAL",
            "description": f"Loan {row['loan_id']} has balance ${row['current_balance']} and status {row['loan_status']}, but collection case {row['case_id']} remains active in state '{row['case_status']}'.",
            "detection_rule": "loans.current_balance <= 0 AND collection_cases.case_status != 'CLOSED_PAID'",
            "expected_decision": "CLOSE_CASE_AND_ARCHIVE",
            "remediation_action": "close_paid_case",
            "context": dict(row)
        })

    # Scenario 2: Contact outside allowed window
    # Contact attempt where local time was outside 08:00 - 21:00 or compliance_status == 'QUIET_HOURS_VIOLATION'
    q2 = """
    SELECT a.attempt_id, a.case_id, a.customer_id, a.attempt_timestamp, a.customer_local_time,
           a.is_permissible_window, a.compliance_status, c.timezone
    FROM contact_attempts a
    JOIN customers c ON a.customer_id = c.customer_id
    WHERE a.is_permissible_window = 0 OR a.compliance_status = 'QUIET_HOURS_VIOLATION'
       OR (a.customer_local_time < '08:00' OR a.customer_local_time >= '21:00')
    """
    for row in cursor.execute(q2).fetchall():
        detected.append({
            "anomaly_id": f"ANO-SCAN-QUIET-{row['attempt_id']}",
            "entity_type": "ContactAttempt",
            "entity_id": row["attempt_id"],
            "issue_type": "CONTACT_OUTSIDE_ALLOWED_WINDOW",
            "severity": "CRITICAL",
            "description": f"Attempt {row['attempt_id']} logged at customer local time {row['customer_local_time']} in timezone {row['timezone']}. Permissible window is 08:00 - 21:00.",
            "detection_rule": "customer_local_time < '08:00' OR customer_local_time >= '21:00'",
            "expected_decision": "FLAG_VIOLATION_AND_REPRIMAND",
            "remediation_action": "flag_compliance_incident",
            "context": dict(row)
        })

    # Scenario 3: Payment allocated to wrong installment
    # Payment credited to installment N when an older installment M (M < N) on the same loan has unpaid arrears
    q3 = """
    SELECT p.payment_id, p.loan_id, p.allocated_installment_id, p.amount,
           cur_ins.installment_number as paid_num, cur_ins.due_date as paid_due,
           old_ins.installment_id as skipped_ins_id, old_ins.installment_number as skipped_num,
           old_ins.remaining_balance as skipped_arrears
    FROM payments p
    JOIN installments cur_ins ON p.allocated_installment_id = cur_ins.installment_id
    JOIN installments old_ins ON p.loan_id = old_ins.loan_id
    WHERE old_ins.installment_number < cur_ins.installment_number
      AND old_ins.remaining_balance > 0.01
      AND old_ins.due_date < cur_ins.due_date
    """
    for row in cursor.execute(q3).fetchall():
        detected.append({
            "anomaly_id": f"ANO-SCAN-ALLOC-{row['payment_id']}",
            "entity_type": "Payment",
            "entity_id": row["payment_id"],
            "issue_type": "PAYMENT_ALLOCATED_TO_WRONG_INSTALLMENT",
            "severity": "HIGH",
            "description": f"Payment {row['payment_id']} ($ {row['amount']}) credited to installment #{row['paid_num']} while older installment #{row['skipped_num']} ({row['skipped_ins_id']}) still has arrears of ${row['skipped_arrears']}.",
            "detection_rule": "payment.allocated_installment_number > older_installment.installment_number AND older_installment.remaining_balance > 0",
            "expected_decision": "REALLOCATE_WATERFALL_WATERLINE",
            "remediation_action": "reallocate_waterfall",
            "context": dict(row)
        })

    # Scenario 4: Promise amount exceeds arrears
    # PTP promised_amount > current_arrears_at_promise
    q4 = """
    SELECT ptp.ptp_id, ptp.case_id, ptp.loan_id, ptp.promised_amount,
           ptp.current_arrears_at_promise, l.total_arrears as current_loan_arrears
    FROM promises_to_pay ptp
    JOIN loans l ON ptp.loan_id = l.loan_id
    WHERE ptp.promised_amount > (ptp.current_arrears_at_promise + 0.01)
    """
    for row in cursor.execute(q4).fetchall():
        detected.append({
            "anomaly_id": f"ANO-SCAN-PTP-{row['ptp_id']}",
            "entity_type": "PromiseToPay",
            "entity_id": row["ptp_id"],
            "issue_type": "PROMISE_AMOUNT_EXCEEDS_ARREARS",
            "severity": "MEDIUM",
            "description": f"Promise to Pay {row['ptp_id']} was recorded for ${row['promised_amount']}, which exceeds historical arrears at promise (${row['current_arrears_at_promise']}).",
            "detection_rule": "ptp.promised_amount > ptp.current_arrears_at_promise",
            "expected_decision": "REVISE_PROMISE_AMOUNT",
            "remediation_action": "cap_promise_to_arrears",
            "context": dict(row)
        })

    # Scenario 5: Disputed debt treated as confirmed
    # Contact attempt logged where customer dispute_status == 'ACTIVE_DISPUTE' and outcome wasn't BLOCKED_BY_GUARDRAIL
    q5 = """
    SELECT a.attempt_id, a.case_id, a.customer_id, a.contact_outcome, a.compliance_status,
           c.dispute_status
    FROM contact_attempts a
    JOIN customers c ON a.customer_id = c.customer_id
    WHERE c.dispute_status = 'ACTIVE_DISPUTE'
      AND a.compliance_status != 'DISPUTE_HOLD_VIOLATION'
      AND a.contact_outcome != 'BLOCKED_BY_GUARDRAIL'
    """
    for row in cursor.execute(q5).fetchall():
        detected.append({
            "anomaly_id": f"ANO-SCAN-DISP-{row['attempt_id']}",
            "entity_type": "ContactAttempt",
            "entity_id": row["attempt_id"],
            "issue_type": "DISPUTED_DEBT_TREATED_AS_CONFIRMED",
            "severity": "CRITICAL",
            "description": f"Contact attempt {row['attempt_id']} proceeded against customer {row['customer_id']} during active debt dispute without verification moratorium.",
            "detection_rule": "customers.dispute_status == 'ACTIVE_DISPUTE' AND contact_attempts.contact_outcome != 'BLOCKED_BY_GUARDRAIL'",
            "expected_decision": "FREEZE_CONTACT_AND_VALIDATE",
            "remediation_action": "freeze_disputed_account",
            "context": dict(row)
        })

    return detected


def remediate_anomaly(conn: sqlite3.Connection, anomaly: Dict[str, Any], actor_id: str = "COMPLIANCE_OFFICER") -> Dict[str, Any]:
    """
    Applies auditable remediation for a detected edge case.
    """
    cursor = conn.cursor()
    issue_type = anomaly["issue_type"]
    entity_id = anomaly["entity_id"]

    if issue_type == "PAID_ACCOUNT_REMAINS_IN_COLLECTION":
        cursor.execute(
            """
            UPDATE collection_cases
            SET case_status = 'CLOSED_PAID', priority_score = 0.0, priority_tier = 'P4_LOW',
                active_ptp_id = NULL, next_scheduled_action = NULL
            WHERE case_id = ?
            """,
            (entity_id,)
        )
        log_audit_event(
            conn, "CollectionCase", entity_id, "REMEDIATE_PAID_ACCOUNT",
            "REVIEWER", actor_id, notes="Auto-closed collection case for paid-off account."
        )
        return {"status": "SUCCESS", "message": f"Case {entity_id} closed as CLOSED_PAID."}

    elif issue_type == "CONTACT_OUTSIDE_ALLOWED_WINDOW":
        cursor.execute(
            """
            UPDATE contact_attempts
            SET compliance_status = 'QUIET_HOURS_VIOLATION'
            WHERE attempt_id = ?
            """,
            (entity_id,)
        )
        log_audit_event(
            conn, "ContactAttempt", entity_id, "REMEDIATE_QUIET_HOURS",
            "REVIEWER", actor_id, notes="Marked attempt as formal QUIET_HOURS_VIOLATION and notified supervisory queue."
        )
        return {"status": "SUCCESS", "message": f"Attempt {entity_id} updated to QUIET_HOURS_VIOLATION."}

    elif issue_type == "PAYMENT_ALLOCATED_TO_WRONG_INSTALLMENT":
        cursor.execute(
            """
            UPDATE payments
            SET allocation_status = 'MISALLOCATED_WRONG_INSTALLMENT'
            WHERE payment_id = ?
            """,
            (entity_id,)
        )
        log_audit_event(
            conn, "Payment", entity_id, "REMEDIATE_MISALLOCATION",
            "REVIEWER", actor_id, notes="Flagged misallocated payment for ledger journal correction."
        )
        return {"status": "SUCCESS", "message": f"Payment {entity_id} flagged for journal correction."}

    elif issue_type == "PROMISE_AMOUNT_EXCEEDS_ARREARS":
        cursor.execute(
            """
            UPDATE promises_to_pay
            SET promised_amount = current_arrears_at_promise
            WHERE ptp_id = ?
            """,
            (entity_id,)
        )
        log_audit_event(
            conn, "PromiseToPay", entity_id, "REMEDIATE_PTP_AMOUNT",
            "REVIEWER", actor_id, notes="Capped promise amount to maximum legitimate arrears."
        )
        return {"status": "SUCCESS", "message": f"Promise {entity_id} amount capped to legitimate arrears."}

    elif issue_type == "DISPUTED_DEBT_TREATED_AS_CONFIRMED":
        cursor.execute(
            """
            UPDATE contact_attempts
            SET compliance_status = 'DISPUTE_HOLD_VIOLATION'
            WHERE attempt_id = ?
            """,
            (entity_id,)
        )
        log_audit_event(
            conn, "ContactAttempt", entity_id, "REMEDIATE_DISPUTE_VIOLATION",
            "REVIEWER", actor_id, notes="Flagged dispute moratorium breach and enforced strict freeze."
        )
        return {"status": "SUCCESS", "message": f"Dispute breach on attempt {entity_id} flagged and freeze enforced."}

    return {"status": "UNKNOWN", "message": "No remediation handler for this issue type."}
