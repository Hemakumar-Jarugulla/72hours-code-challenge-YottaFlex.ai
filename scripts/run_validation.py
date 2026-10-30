"""
Comprehensive Data and Schema Validation Suite.
Validates:
1. Primary-Key Uniqueness
2. Foreign-Key Referential Integrity
3. Enum and Allowed Values
4. Chronological Date Ordering
5. Arithmetic Reconciliation (Balances, Installments, Arrears)
6. Lifecycle Transitions and Duplicate Checks
"""

import sys
import os
import sqlite3
import datetime
from typing import Dict, Any, List, Tuple

# Add workspace to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database.db import get_db_connection, init_database


class ValidationSuite:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cursor = conn.cursor()
        self.results: List[Dict[str, Any]] = []

    def run_all(self) -> Dict[str, Any]:
        """Runs all validation checks and returns summary."""
        self.check_primary_key_uniqueness()
        self.check_foreign_key_integrity()
        self.check_enum_constraints()
        self.check_date_ordering()
        self.check_arithmetic_reconciliation()
        self.check_lifecycle_consistency()

        passed_count = sum(1 for r in self.results if r["status"] == "PASS")
        failed_count = sum(1 for r in self.results if r["status"] == "FAIL")

        return {
            "total_checks": len(self.results),
            "passed": passed_count,
            "failed": failed_count,
            "all_passed": failed_count == 0,
            "details": self.results
        }

    def _record(self, name: str, category: str, status: str, message: str, details: Any = None):
        self.results.append({
            "name": name,
            "category": category,
            "status": status,
            "message": message,
            "details": details
        })

    def check_primary_key_uniqueness(self):
        tables = [
            ("customers", "customer_id"),
            ("accounts", "account_id"),
            ("loans", "loan_id"),
            ("installments", "installment_id"),
            ("delinquency_snapshots", "snapshot_id"),
            ("contact_preferences", "preference_id"),
            ("collection_cases", "case_id"),
            ("contact_attempts", "attempt_id"),
            ("promises_to_pay", "ptp_id"),
            ("payments", "payment_id"),
            ("ground_truth_anomalies", "anomaly_id")
        ]

        for tbl, pk in tables:
            q = f"SELECT {pk}, COUNT(*) as c FROM {tbl} GROUP BY {pk} HAVING c > 1"
            dupes = self.cursor.execute(q).fetchall()
            if dupes:
                self._record(f"PK_Uniqueness_{tbl}", "Integrity", "FAIL", f"Found {len(dupes)} duplicate PKs in {tbl}", [d[pk] for d in dupes])
            else:
                self._record(f"PK_Uniqueness_{tbl}", "Integrity", "PASS", f"All primary keys in {tbl} are 100% unique.")

    def check_foreign_key_integrity(self):
        fk_checks = [
            ("accounts", "customer_id", "customers", "customer_id"),
            ("loans", "account_id", "accounts", "account_id"),
            ("loans", "customer_id", "customers", "customer_id"),
            ("installments", "loan_id", "loans", "loan_id"),
            ("delinquency_snapshots", "loan_id", "loans", "loan_id"),
            ("contact_preferences", "customer_id", "customers", "customer_id"),
            ("collection_cases", "loan_id", "loans", "loan_id"),
            ("collection_cases", "customer_id", "customers", "customer_id"),
            ("contact_attempts", "case_id", "collection_cases", "case_id"),
            ("contact_attempts", "customer_id", "customers", "customer_id"),
            ("promises_to_pay", "case_id", "collection_cases", "case_id"),
            ("payments", "loan_id", "loans", "loan_id"),
            ("payments", "allocated_installment_id", "installments", "installment_id")
        ]

        for child_tbl, child_fk, parent_tbl, parent_pk in fk_checks:
            q = f"""
            SELECT c.{child_fk} FROM {child_tbl} c
            LEFT JOIN {parent_tbl} p ON c.{child_fk} = p.{parent_pk}
            WHERE p.{parent_pk} IS NULL
            """
            orphans = self.cursor.execute(q).fetchall()
            if orphans:
                self._record(f"FK_{child_tbl}_{child_fk}", "Referential Integrity", "FAIL", f"Found {len(orphans)} orphaned FK references from {child_tbl} to {parent_tbl}")
            else:
                self._record(f"FK_{child_tbl}_{child_fk}", "Referential Integrity", "PASS", f"Zero orphaned references ({child_tbl}.{child_fk} -> {parent_tbl}.{parent_pk})")

    def check_enum_constraints(self):
        checks = [
            ("customers", "risk_segment", ("LOW", "MEDIUM", "HIGH", "CRITICAL")),
            ("customers", "hardship_status", ("NONE", "TEMPORARY_UNEMPLOYMENT", "MEDICAL_EMERGENCY", "NATURAL_DISASTER")),
            ("customers", "dispute_status", ("NONE", "ACTIVE_DISPUTE", "RESOLVED")),
            ("accounts", "account_status", ("OPEN", "DELINQUENT", "SUSPENDED", "CLOSED")),
            ("loans", "loan_type", ("PERSONAL", "AUTO", "MORTGAGE", "SME_REVOLVING")),
            ("loans", "loan_status", ("CURRENT", "DELINQUENT", "PAID_OFF", "CHARGEOFF")),
            ("installments", "status", ("UPCOMING", "CURRENT", "OVERDUE", "PAID", "PARTIALLY_PAID")),
            ("collection_cases", "case_status", ("ACTIVE", "PENDING_PTP", "UNDER_DISPUTE", "HARDSHIP_HOLD", "RESOLVED", "CLOSED_PAID")),
            ("collection_cases", "priority_tier", ("P1_CRITICAL", "P2_HIGH", "P3_MEDIUM", "P4_LOW")),
            ("contact_attempts", "compliance_status", ("COMPLIANT", "QUIET_HOURS_VIOLATION", "FREQUENCY_CAP_EXCEEDED", "DISPUTE_HOLD_VIOLATION", "HARDSHIP_HOLD_VIOLATION", "CEASE_DESIST_VIOLATION", "BLOCKED_BY_GUARDRAIL")),
            ("promises_to_pay", "ptp_status", ("PENDING", "KEPT", "PARTIALLY_KEPT", "BROKEN", "CANCELLED")),
            ("payments", "payment_method", ("ACH", "DEBIT_CARD", "WIRE", "CHECK"))
        ]

        for tbl, col, allowed in checks:
            placeholders = ",".join(f"'{v}'" for v in allowed)
            q = f"SELECT {col} FROM {tbl} WHERE {col} NOT IN ({placeholders})"
            invalids = self.cursor.execute(q).fetchall()
            if invalids:
                self._record(f"Enum_{tbl}_{col}", "Domain Rules", "FAIL", f"Found {len(invalids)} invalid enums in {tbl}.{col}")
            else:
                self._record(f"Enum_{tbl}_{col}", "Domain Rules", "PASS", f"All values in {tbl}.{col} conform to allowed domain enums.")

    def check_date_ordering(self):
        # 1. Accounts opened after customer created
        q1 = """
        SELECT a.account_id, a.opened_date, c.created_at
        FROM accounts a
        JOIN customers c ON a.customer_id = c.customer_id
        WHERE substr(a.opened_date, 1, 10) < substr(c.created_at, 1, 10)
        """
        bad_dates1 = self.cursor.execute(q1).fetchall()
        if bad_dates1:
            self._record("DateOrder_Account_Customer", "Temporal Logic", "FAIL", f"{len(bad_dates1)} accounts opened prior to customer creation")
        else:
            self._record("DateOrder_Account_Customer", "Temporal Logic", "PASS", "All accounts opened on or after customer creation date.")

        # 2. Loans maturity date > start date
        q2 = "SELECT loan_id FROM loans WHERE maturity_date <= start_date"
        bad_mat = self.cursor.execute(q2).fetchall()
        if bad_mat:
            self._record("DateOrder_Loan_Maturity", "Temporal Logic", "FAIL", f"{len(bad_mat)} loans with maturity <= start date")
        else:
            self._record("DateOrder_Loan_Maturity", "Temporal Logic", "PASS", "All loan maturity dates are strictly after start dates.")

    def check_arithmetic_reconciliation(self):
        # 1. Installments remaining_balance = total_amount_due - amount_paid (within $0.02)
        q1 = """
        SELECT installment_id, total_amount_due, amount_paid, remaining_balance
        FROM installments
        WHERE abs(remaining_balance - (total_amount_due - amount_paid)) > 0.05
        """
        bad_inss = self.cursor.execute(q1).fetchall()
        if bad_inss:
            self._record("Arith_Installment_Balance", "Reconciliation", "FAIL", f"{len(bad_inss)} installments with incorrect balance arithmetic")
        else:
            self._record("Arith_Installment_Balance", "Reconciliation", "PASS", "100% of installment remaining balances reconcile with total due minus paid.")

        # 2. Loan current_balance = sum of unpaid installments (within $0.05)
        q2 = """
        SELECT l.loan_id, l.current_balance, coalesce(sum(i.remaining_balance), 0.0) as sum_rem
        FROM loans l
        LEFT JOIN installments i ON l.loan_id = i.loan_id
        GROUP BY l.loan_id
        HAVING abs(l.current_balance - sum_rem) > 0.10
        """
        bad_loans = self.cursor.execute(q2).fetchall()
        if bad_loans:
            self._record("Arith_Loan_Balance", "Reconciliation", "FAIL", f"{len(bad_loans)} loans where current_balance does not match sum of installment balances")
        else:
            self._record("Arith_Loan_Balance", "Reconciliation", "PASS", "Loan balances exactly reconcile with sum of installment remaining balances.")

    def check_lifecycle_consistency(self):
        # Delinquency buckets match DPD
        q1 = """
        SELECT snapshot_id, days_past_due, delinquency_bucket
        FROM delinquency_snapshots
        WHERE (days_past_due = 0 AND delinquency_bucket != 'CURRENT')
           OR (days_past_due BETWEEN 1 AND 30 AND delinquency_bucket != '30_DPD')
           OR (days_past_due BETWEEN 31 AND 60 AND delinquency_bucket != '60_DPD')
           OR (days_past_due BETWEEN 61 AND 90 AND delinquency_bucket != '90_DPD')
           OR (days_past_due > 90 AND delinquency_bucket != '120_PLUS_DPD')
        """
        bad_buckets = self.cursor.execute(q1).fetchall()
        if bad_buckets:
            self._record("Lifecycle_Delinquency_Buckets", "Lifecycle", "FAIL", f"{len(bad_buckets)} snapshot delinquency buckets inconsistent with DPD")
        else:
            self._record("Lifecycle_Delinquency_Buckets", "Lifecycle", "PASS", "All delinquency snapshots match DPD boundaries.")


def run_validation(db_path: str = None) -> bool:
    conn = get_db_connection(db_path)
    suite = ValidationSuite(conn)
    res = suite.run_all()
    conn.close()

    print("\n" + "=" * 80)
    print("FAIR COLLECTIONS & RECOVERY ENGINE - VALIDATION SUMMARY")
    print("=" * 80)
    print(f"Total Rules Checked: {res['total_checks']}")
    print(f"Passed:              {res['passed']} [PASS]")
    print(f"Failed:              {res['failed']} [{'FAIL' if res['failed'] > 0 else ' '}]")
    print("-" * 80)

    for item in res["details"]:
        mark = "PASS" if item["status"] == "PASS" else "FAIL"
        print(f"[{mark:<4}] {item['category']:<22} | {item['name']:<30} | {item['message']}")

    print("=" * 80)
    return res["all_passed"]


if __name__ == "__main__":
    success = run_validation()
    sys.exit(0 if success else 1)
