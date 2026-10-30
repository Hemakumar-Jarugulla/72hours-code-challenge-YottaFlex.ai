"""
Commitment Monitoring & Waterfall Payment Allocation Engine.
Implements chronological amortization waterfall allocation and reconciles
incoming payments against Promises to Pay (PTP).
"""

import datetime
from typing import Dict, Any, List, Optional
import sqlite3
from database.db import log_audit_event


def allocate_payment_waterfall(
    conn: sqlite3.Connection,
    loan_id: str,
    payment_amount: float,
    payment_date: str,
    payment_method: str = "ACH",
    ptp_id: Optional[str] = None,
    actor_persona: str = "SYSTEM",
    actor_id: str = "SYS-PAYMENT-ENGINE"
) -> Dict[str, Any]:
    """
    Allocates a payment across installments strictly adhering to chronological waterfall logic:
    Oldest overdue installment is satisfied first, then the next oldest.
    Reconciles any matching active Promise to Pay (PTP).
    If loan balance reaches 0, auto-closes the collection case.
    """
    cursor = conn.cursor()

    # 1. Fetch loan and customer details
    loan = cursor.execute("SELECT * FROM loans WHERE loan_id = ?", (loan_id,)).fetchone()
    if not loan:
        raise ValueError(f"Loan {loan_id} not found")

    customer_id = loan["customer_id"]
    account_id = loan["account_id"]

    # 2. Fetch unpaid or partially paid installments ordered by due date
    installments = cursor.execute(
        """
        SELECT * FROM installments
        WHERE loan_id = ? AND status IN ('OVERDUE', 'PARTIALLY_PAID', 'CURRENT', 'UPCOMING')
        ORDER BY due_date ASC, installment_number ASC
        """,
        (loan_id,)
    ).fetchall()

    remaining_payment = round(payment_amount, 2)
    allocations = []
    first_allocated_ins_id = None

    for ins in installments:
        if remaining_payment <= 0.001:
            break

        ins_id = ins["installment_id"]
        ins_rem = round(ins["remaining_balance"], 2)
        
        if ins_rem <= 0:
            continue

        if not first_allocated_ins_id:
            first_allocated_ins_id = ins_id

        alloc_amount = min(remaining_payment, ins_rem)
        new_amount_paid = round(ins["amount_paid"] + alloc_amount, 2)
        new_rem_balance = round(ins["total_amount_due"] - new_amount_paid, 2)
        
        new_status = "PAID" if new_rem_balance <= 0.001 else "PARTIALLY_PAID"
        new_days_overdue = 0 if new_status == "PAID" else ins["days_overdue"]

        cursor.execute(
            """
            UPDATE installments
            SET amount_paid = ?, remaining_balance = ?, status = ?, days_overdue = ?
            WHERE installment_id = ?
            """,
            (new_amount_paid, new_rem_balance, new_status, new_days_overdue, ins_id)
        )

        allocations.append({
            "installment_id": ins_id,
            "allocated_amount": alloc_amount,
            "remaining_balance": new_rem_balance,
            "status": new_status
        })

        remaining_payment = round(remaining_payment - alloc_amount, 2)

    # 3. Insert Payment record
    # Generate deterministic payment ID
    count_row = cursor.execute("SELECT COUNT(*) as c FROM payments").fetchone()
    next_num = (count_row["c"] if count_row else 0) + 1
    payment_id = f"PMT-2026-{next_num:06d}"
    ref_code = f"REF-{next_num:06d}X{int(payment_amount)}"

    primary_ins_id = first_allocated_ins_id or (installments[0]["installment_id"] if installments else "INS-UNKNOWN")

    cursor.execute(
        """
        INSERT INTO payments (
            payment_id, loan_id, account_id, customer_id, payment_date,
            amount, payment_method, allocated_installment_id, allocation_status,
            reconciled_ptp_id, payment_reference
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payment_id, loan_id, account_id, customer_id, payment_date,
            payment_amount, payment_method, primary_ins_id, "ALLOCATED_CORRECTLY",
            ptp_id, ref_code
        )
    )

    # 4. Recalculate Loan arrears, balance, and days past due
    unpaid_rows = cursor.execute(
        """
        SELECT remaining_balance, due_date FROM installments
        WHERE loan_id = ? AND remaining_balance > 0.001
        ORDER BY due_date ASC
        """,
        (loan_id,)
    ).fetchall()

    new_loan_balance = round(sum(r["remaining_balance"] for r in unpaid_rows), 2)
    
    # Overdue arrears: installments whose due_date <= payment_date
    overdue_rows = [r for r in unpaid_rows if r["due_date"] <= payment_date]
    new_total_arrears = round(sum(r["remaining_balance"] for r in overdue_rows), 2)

    if overdue_rows:
        oldest_due = datetime.date.fromisoformat(overdue_rows[0]["due_date"])
        pay_dt = datetime.date.fromisoformat(payment_date)
        new_dpd = max(0, (pay_dt - oldest_due).days)
    else:
        new_dpd = 0

    new_loan_status = "PAID_OFF" if new_loan_balance <= 0.001 else ("DELINQUENT" if new_total_arrears > 0.001 else "CURRENT")

    cursor.execute(
        """
        UPDATE loans
        SET current_balance = ?, total_arrears = ?, days_past_due = ?, loan_status = ?
        WHERE loan_id = ?
        """,
        (new_loan_balance, new_total_arrears, new_dpd, new_loan_status, loan_id)
    )

    # 5. Reconcile with PromiseToPay
    ptp_reconciliation_result = None
    if ptp_id:
        ptp = cursor.execute("SELECT * FROM promises_to_pay WHERE ptp_id = ?", (ptp_id,)).fetchone()
        if ptp:
            prev_fulfilled = ptp["fulfilled_amount"] or 0.0
            new_fulfilled = round(prev_fulfilled + payment_amount, 2)
            promised_amt = ptp["promised_amount"]

            if new_fulfilled >= promised_amt:
                ptp_status = "KEPT"
            elif new_fulfilled > 0.0:
                ptp_status = "PARTIALLY_KEPT"
            else:
                ptp_status = ptp["ptp_status"]

            cursor.execute(
                """
                UPDATE promises_to_pay
                SET fulfilled_amount = ?, fulfillment_date = ?, ptp_status = ?, reconciled_payment_id = ?
                WHERE ptp_id = ?
                """,
                (new_fulfilled, payment_date, ptp_status, payment_id, ptp_id)
            )

            ptp_reconciliation_result = {
                "ptp_id": ptp_id,
                "status": ptp_status,
                "promised_amount": promised_amt,
                "fulfilled_amount": new_fulfilled
            }

    # 6. Update CollectionCase lifecycle
    case = cursor.execute("SELECT * FROM collection_cases WHERE loan_id = ?", (loan_id,)).fetchone()
    case_updated_status = None
    if case:
        case_id = case["case_id"]
        if new_loan_status == "PAID_OFF":
            case_updated_status = "CLOSED_PAID"
            cursor.execute(
                """
                UPDATE collection_cases
                SET case_status = 'CLOSED_PAID', priority_score = 0.0, priority_tier = 'P4_LOW',
                    active_ptp_id = NULL, next_scheduled_action = NULL
                WHERE case_id = ?
                """,
                (case_id,)
            )
            log_audit_event(
                conn, "CollectionCase", case_id, "AUTO_CLOSE_PAID",
                actor_persona, actor_id, previous_state=case["case_status"], new_state="CLOSED_PAID",
                notes=f"Loan {loan_id} fully amortized and paid off."
            )
        elif ptp_reconciliation_result and ptp_reconciliation_result["status"] == "KEPT":
            # If PTP was kept and arrears still remain, transition back to active monitoring or resolved
            case_updated_status = "RESOLVED" if new_total_arrears <= 0.001 else "ACTIVE"
            cursor.execute(
                """
                UPDATE collection_cases
                SET case_status = ?, active_ptp_id = NULL
                WHERE case_id = ?
                """,
                (case_updated_status, case_id)
            )

    log_audit_event(
        conn, "Payment", payment_id, "ALLOCATE_PAYMENT_WATERFALL",
        actor_persona, actor_id, notes=f"Paid ${payment_amount} across {len(allocations)} installments."
    )

    return {
        "payment_id": payment_id,
        "amount": payment_amount,
        "allocations": allocations,
        "unallocated_remainder": remaining_payment,
        "loan_status": new_loan_status,
        "new_balance": new_loan_balance,
        "new_arrears": new_total_arrears,
        "new_dpd": new_dpd,
        "ptp_reconciliation": ptp_reconciliation_result,
        "case_status": case_updated_status
    }


def evaluate_overdue_ptps(conn: sqlite3.Connection, reference_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Scans pending promises to pay past their due date (+ 1-day grace period)
    and marks them BROKEN if unfulfilled.
    """
    cursor = conn.cursor()
    if not reference_date:
        reference_date = datetime.date.today().isoformat()

    ref_dt = datetime.date.fromisoformat(reference_date)

    pending_ptps = cursor.execute(
        "SELECT * FROM promises_to_pay WHERE ptp_status = 'PENDING'"
    ).fetchall()

    broken_list = []
    for ptp in pending_ptps:
        due_dt = datetime.date.fromisoformat(ptp["promise_due_date"])
        # Grace period: 1 day
        if (ref_dt - due_dt).days > 1:
            fulfilled = ptp["fulfilled_amount"] or 0.0
            new_status = "PARTIALLY_KEPT" if fulfilled > 0.0 else "BROKEN"
            
            cursor.execute(
                "UPDATE promises_to_pay SET ptp_status = ? WHERE ptp_id = ?",
                (new_status, ptp["ptp_id"])
            )

            # Re-activate collection case from PENDING_PTP
            cursor.execute(
                "UPDATE collection_cases SET case_status = 'ACTIVE', active_ptp_id = NULL WHERE case_id = ?",
                (ptp["case_id"],)
            )

            log_audit_event(
                conn, "PromiseToPay", ptp["ptp_id"], "EXPIRE_PTP",
                "SYSTEM", "SYS-PTP-MONITOR", previous_state="PENDING", new_state=new_status,
                notes=f"Promise expired on {ptp['promise_due_date']}; fulfilled ${fulfilled} of ${ptp['promised_amount']}."
            )

            broken_list.append({
                "ptp_id": ptp["ptp_id"],
                "case_id": ptp["case_id"],
                "new_status": new_status,
                "promised_amount": ptp["promised_amount"],
                "fulfilled_amount": fulfilled
            })

    return broken_list
