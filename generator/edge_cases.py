"""
Edge Case & Anomaly Injection Module.
Injects labelled negative scenarios strictly according to business requirements:
1. Paid account remains in collection
2. Contact outside allowed window
3. Payment allocated to wrong installment
4. Promise amount exceeds arrears
5. Disputed debt treated as confirmed

Outputs separate Ground Truth records that are never leaked into operational feature tables.
"""

import random
from typing import List, Dict, Any, Tuple
from generator.models import (
    CustomerModel, LoanModel, InstallmentModel, CollectionCaseModel,
    ContactAttemptModel, PromiseToPayModel, PaymentModel, GroundTruthAnomalyModel
)


def inject_edge_cases(
    customers: List[CustomerModel],
    loans: List[LoanModel],
    installments: List[InstallmentModel],
    collection_cases: List[CollectionCaseModel],
    contact_attempts: List[ContactAttemptModel],
    promises: List[PromiseToPayModel],
    payments: List[PaymentModel],
    anomaly_counts: Dict[str, int],
    rng: random.Random
) -> List[GroundTruthAnomalyModel]:
    """
    Injects labelled negative scenarios into pre-generated clean baseline records.
    Returns list of GroundTruthAnomalyModel items for validation.
    """
    anomalies: List[GroundTruthAnomalyModel] = []
    anomaly_counter = 1

    # Map lookups for fast access
    cust_by_id = {c.customer_id: c for c in customers}
    loans_by_id = {l.loan_id: l for l in loans}
    cases_by_loan = {c.loan_id: c for c in collection_cases}
    ins_by_loan: Dict[str, List[InstallmentModel]] = {}
    for ins in installments:
        ins_by_loan.setdefault(ins.loan_id, []).append(ins)

    # -------------------------------------------------------------
    # Scenario 1: Paid account remains in collection
    # -------------------------------------------------------------
    count_scen1 = min(len(collection_cases), anomaly_counts.get("PAID_ACCOUNT_REMAINS_IN_COLLECTION", 5))
    target_cases_scen1 = rng.sample(collection_cases, count_scen1) if collection_cases else []

    for case in target_cases_scen1:
        l = loans_by_id.get(case.loan_id)
        if l:
            # Mark the loan as fully paid off, but leave the case ACTIVE
            l.current_balance = 0.0
            l.total_arrears = 0.0
            l.days_past_due = 0
            l.loan_status = "PAID_OFF"

            # Satisfy all installments on this loan
            for ins in ins_by_loan.get(l.loan_id, []):
                ins.amount_paid = ins.total_amount_due
                ins.remaining_balance = 0.0
                ins.days_overdue = 0
                ins.status = "PAID"

            case.case_status = "ACTIVE"
            case.priority_score = 82.5
            case.priority_tier = "P1_CRITICAL"
            case.next_scheduled_action = "2026-11-05T14:00:00Z"

            ano_id = f"ANO-{anomaly_counter:06d}"
            anomaly_counter += 1
            anomalies.append(GroundTruthAnomalyModel(
                anomaly_id=ano_id,
                entity_type="CollectionCase",
                entity_id=case.case_id,
                issue_type="PAID_ACCOUNT_REMAINS_IN_COLLECTION",
                description=f"Loan {l.loan_id} has $0.00 balance (PAID_OFF) but collection case {case.case_id} remains ACTIVE.",
                expected_decision="CLOSE_CASE_AND_ARCHIVE",
                detection_rule="loans.current_balance <= 0 AND collection_cases.case_status != 'CLOSED_PAID'",
                severity="CRITICAL"
            ))

    # -------------------------------------------------------------
    # Scenario 2: Contact outside allowed window
    # -------------------------------------------------------------
    count_scen2 = min(len(contact_attempts), anomaly_counts.get("CONTACT_OUTSIDE_ALLOWED_WINDOW", 8))
    target_attempts = rng.sample(contact_attempts, count_scen2) if contact_attempts else []

    for att in target_attempts:
        # Alter timestamp to late night (e.g. 23:45 or 03:15)
        bad_hour = rng.choice(["23:45", "02:30", "04:15"])
        att.customer_local_time = bad_hour
        att.is_permissible_window = 0
        att.compliance_status = "QUIET_HOURS_VIOLATION"
        att.contact_outcome = "VOICEMAIL_LEFT"
        att.agent_notes = "Outreach attempted during quiet hours without emergency exception."

        ano_id = f"ANO-{anomaly_counter:06d}"
        anomaly_counter += 1
        anomalies.append(GroundTruthAnomalyModel(
            anomaly_id=ano_id,
            entity_type="ContactAttempt",
            entity_id=att.attempt_id,
            issue_type="CONTACT_OUTSIDE_ALLOWED_WINDOW",
            description=f"Contact attempt {att.attempt_id} logged at prohibited consumer local time {bad_hour}.",
            expected_decision="FLAG_VIOLATION_AND_REPRIMAND",
            detection_rule="customer_local_time < '08:00' OR customer_local_time >= '21:00'",
            severity="CRITICAL"
        ))

    # -------------------------------------------------------------
    # Scenario 3: Payment allocated to wrong installment
    # -------------------------------------------------------------
    count_scen3 = min(len(payments), anomaly_counts.get("PAYMENT_ALLOCATED_TO_WRONG_INSTALLMENT", 6))
    # Pick payments on loans with at least 2 installments
    eligible_pmts = [p for p in payments if len(ins_by_loan.get(p.loan_id, [])) >= 2]
    target_payments = rng.sample(eligible_pmts, count_scen3) if eligible_pmts else []

    for pmt in target_payments:
        inss = ins_by_loan.get(pmt.loan_id, [])
        if len(inss) >= 2:
            # Ensure the older installment has an unpaid balance
            skipped_old = inss[0]
            wrong_target = inss[-1]
            skipped_old.remaining_balance = round(skipped_old.total_amount_due * 0.8, 2)
            skipped_old.status = "OVERDUE"
            skipped_old.amount_paid = round(skipped_old.total_amount_due - skipped_old.remaining_balance, 2)

            # Keep loan current_balance and total_arrears reconciled with installments
            target_loan = loans_by_id.get(pmt.loan_id)
            if target_loan:
                target_loan.current_balance = round(sum(i.remaining_balance for i in inss), 2)
                target_loan.total_arrears = round(sum(i.remaining_balance for i in inss if i.status == "OVERDUE"), 2)

            pmt.allocated_installment_id = wrong_target.installment_id
            pmt.allocation_status = "MISALLOCATED_WRONG_INSTALLMENT"

            ano_id = f"ANO-{anomaly_counter:06d}"
            anomaly_counter += 1
            anomalies.append(GroundTruthAnomalyModel(
                anomaly_id=ano_id,
                entity_type="Payment",
                entity_id=pmt.payment_id,
                issue_type="PAYMENT_ALLOCATED_TO_WRONG_INSTALLMENT",
                description=f"Payment {pmt.payment_id} (${pmt.amount}) credited to installment {wrong_target.installment_id} while earlier installment {skipped_old.installment_id} has unpaid arrears.",
                expected_decision="REALLOCATE_WATERFALL_WATERLINE",
                detection_rule="payment.allocated_installment_number > older_installment.installment_number AND older_installment.remaining_balance > 0",
                severity="HIGH"
            ))

    # -------------------------------------------------------------
    # Scenario 4: Promise amount exceeds arrears
    # -------------------------------------------------------------
    count_scen4 = min(len(promises), anomaly_counts.get("PROMISE_AMOUNT_EXCEEDS_ARREARS", 5))
    target_promises = rng.sample(promises, count_scen4) if promises else []

    for ptp in target_promises:
        # Inflate promised amount to 3x arrears
        base_arrears = max(100.0, ptp.current_arrears_at_promise)
        inflated_promise = round(base_arrears * 3.5, 2)
        ptp.promised_amount = inflated_promise

        ano_id = f"ANO-{anomaly_counter:06d}"
        anomaly_counter += 1
        anomalies.append(GroundTruthAnomalyModel(
            anomaly_id=ano_id,
            entity_type="PromiseToPay",
            entity_id=ptp.ptp_id,
            issue_type="PROMISE_AMOUNT_EXCEEDS_ARREARS",
            description=f"Promise {ptp.ptp_id} committed amount ${inflated_promise} exceeds actual arrears ${base_arrears}.",
            expected_decision="REVISE_PROMISE_AMOUNT",
            detection_rule="ptp.promised_amount > ptp.current_arrears_at_promise",
            severity="MEDIUM"
        ))

    # -------------------------------------------------------------
    # Scenario 5: Disputed debt treated as confirmed
    # -------------------------------------------------------------
    dispute_custs = [c for c in customers if c.dispute_status == "ACTIVE_DISPUTE"]
    if not dispute_custs and customers:
        # Ensure at least some customers have ACTIVE_DISPUTE
        for c in customers[:5]:
            c.dispute_status = "ACTIVE_DISPUTE"
            dispute_custs.append(c)

    count_scen5 = min(len(dispute_custs), anomaly_counts.get("DISPUTED_DEBT_TREATED_AS_CONFIRMED", 6))
    target_disp_custs = rng.sample(dispute_custs, count_scen5) if dispute_custs else []

    for c in target_disp_custs:
        # Find or create a contact attempt against this customer that unlawfully bypassed dispute hold
        matching_attempts = [a for a in contact_attempts if a.customer_id == c.customer_id]
        if matching_attempts:
            att = matching_attempts[0]
            att.compliance_status = "COMPLIANT"  # False positive / improper bypass
            att.contact_outcome = "CONNECTED_REFUSED_TO_PAY"
            att.agent_notes = "Demanded immediate payment despite debtor verbal dispute."

            ano_id = f"ANO-{anomaly_counter:06d}"
            anomaly_counter += 1
            anomalies.append(GroundTruthAnomalyModel(
                anomaly_id=ano_id,
                entity_type="ContactAttempt",
                entity_id=att.attempt_id,
                issue_type="DISPUTED_DEBT_TREATED_AS_CONFIRMED",
                description=f"Contact attempt {att.attempt_id} proceeded against customer {c.customer_id} during active dispute without validation notice.",
                expected_decision="FREEZE_CONTACT_AND_VALIDATE",
                detection_rule="customers.dispute_status == 'ACTIVE_DISPUTE' AND contact_attempts.contact_outcome != 'BLOCKED_BY_GUARDRAIL'",
                severity="CRITICAL"
            ))

    return anomalies
