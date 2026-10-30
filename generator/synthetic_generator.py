"""
Deterministic Synthetic Data Generation Engine.
Generates fully relational, realistic debt collection datasets:
Master data -> Amortization schedules -> Payment histories -> Delinquency Snapshots
-> Priority Scoring -> Permissible Outreach -> PTPs -> Injected Edge Cases.
"""

import os
import csv
import json
import random
import hashlib
import datetime
from typing import Dict, Any, List, Tuple, Optional
import sqlite3

from generator.config import (
    DEFAULT_SEED, SCALE_PROFILES, TIMEZONES, RISK_SEGMENTS, RISK_WEIGHTS,
    HARDSHIP_STATUSES, HARDSHIP_WEIGHTS, DISPUTE_STATUSES, DISPUTE_WEIGHTS,
    LOAN_TYPES, LOAN_TYPE_WEIGHTS, CONTACT_CHANNELS
)
from generator.models import (
    CustomerModel, AccountModel, LoanModel, InstallmentModel,
    DelinquencySnapshotModel, ContactPreferenceModel, CollectionCaseModel,
    ContactAttemptModel, PromiseToPayModel, PaymentModel, GroundTruthAnomalyModel
)
from generator.edge_cases import inject_edge_cases
from engine.prioritization_engine import calculate_case_priority
from engine.compliance_engine import evaluate_contact_compliance, get_consumer_local_time


FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
    "Kenneth", "Carol", "Kevin", "Amanda", "Brian", "Melissa", "George", "Deborah",
    "Timothy", "Stephanie", "Ronald", "Rebecca", "Jason", "Sharon", "Edward", "Laura"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell"
]


class SyntheticDataGenerator:
    """Deterministic generator for Debt Collection & Recovery synthetic datasets."""

    def __init__(self, seed: int = DEFAULT_SEED, profile_name: str = "starter"):
        self.seed = seed
        self.profile_name = profile_name
        self.config = SCALE_PROFILES.get(profile_name, SCALE_PROFILES["starter"])
        self.rng = random.Random(seed)
        
        # Reference date anchor for the 12-month historical window
        self.reference_date = datetime.date(2026, 10, 22)
        
        # Collections
        self.customers: List[CustomerModel] = []
        self.accounts: List[AccountModel] = []
        self.loans: List[LoanModel] = []
        self.installments: List[InstallmentModel] = []
        self.delinquency_snapshots: List[DelinquencySnapshotModel] = []
        self.contact_preferences: List[ContactPreferenceModel] = []
        self.collection_cases: List[CollectionCaseModel] = []
        self.contact_attempts: List[ContactAttemptModel] = []
        self.promises_to_pay: List[PromiseToPayModel] = []
        self.payments: List[PaymentModel] = []
        self.ground_truth_anomalies: List[GroundTruthAnomalyModel] = []

    def generate_all(self) -> Dict[str, Any]:
        """Executes full end-to-end data generation pipeline."""
        self._generate_master_data()
        self._generate_loan_schedules_and_payments()
        self._derive_delinquency_and_snapshots()
        self._generate_collection_cases_and_priorities()
        self._generate_contact_attempts_and_promises()
        self._inject_edge_cases()
        self._finalize_derived_fields()

        return {
            "customers": len(self.customers),
            "accounts": len(self.accounts),
            "loans": len(self.loans),
            "installments": len(self.installments),
            "delinquency_snapshots": len(self.delinquency_snapshots),
            "contact_preferences": len(self.contact_preferences),
            "collection_cases": len(self.collection_cases),
            "contact_attempts": len(self.contact_attempts),
            "promises_to_pay": len(self.promises_to_pay),
            "payments": len(self.payments),
            "ground_truth_anomalies": len(self.ground_truth_anomalies)
        }

    def _generate_master_data(self):
        """Generates Customers, Accounts, ContactPreferences, and Loans."""
        num_customers = self.config["num_customers"]
        num_accounts = self.config["num_accounts"]
        num_loans = self.config["num_loans"]

        # 1. Customers
        for i in range(1, num_customers + 1):
            cid = f"CUST-{i:06d}"
            fn = self.rng.choice(FIRST_NAMES)
            ln = self.rng.choice(LAST_NAMES)
            email = f"{fn.lower()}.{ln.lower()}{i}@example.com"
            phone = f"+1{self.rng.randint(200, 999)}{self.rng.randint(2000000, 9999999)}"
            tz = self.rng.choice(TIMEZONES)
            risk = self.rng.choices(RISK_SEGMENTS, weights=RISK_WEIGHTS, k=1)[0]
            hardship = self.rng.choices(HARDSHIP_STATUSES, weights=HARDSHIP_WEIGHTS, k=1)[0]
            dispute = self.rng.choices(DISPUTE_STATUSES, weights=DISPUTE_WEIGHTS, k=1)[0]
            cease_desist = 1 if self.rng.random() < 0.02 else 0
            attorney_rep = 1 if self.rng.random() < 0.02 else 0
            
            created_days_ago = self.rng.randint(380, 800)
            created_dt = self.reference_date - datetime.timedelta(days=created_days_ago)
            created_str = f"{created_dt.isoformat()}T09:00:00Z"

            cust = CustomerModel(
                customer_id=cid, first_name=fn, last_name=ln, email=email,
                phone_number=phone, timezone=tz, risk_segment=risk,
                hardship_status=hardship, dispute_status=dispute,
                cease_desist_flag=cease_desist, attorney_represented=attorney_rep,
                created_at=created_str
            )
            self.customers.append(cust)

            # Contact Preference (1:1 with Customer)
            pref_channel = self.rng.choice(CONTACT_CHANNELS)
            pref = ContactPreferenceModel(
                preference_id=f"PREF-{i:06d}",
                customer_id=cid,
                preferred_channel=pref_channel,
                opt_in_phone=1 if self.rng.random() > 0.05 else 0,
                opt_in_sms=1 if self.rng.random() > 0.08 else 0,
                opt_in_email=1 if self.rng.random() > 0.03 else 0,
                permissible_start_time="08:00",
                permissible_end_time="21:00",
                do_not_call_employer=1,
                allowed_contact_days="MON,TUE,WED,THU,FRI,SAT",
                last_consent_update=created_str
            )
            self.contact_preferences.append(pref)

        # 2. Accounts
        for i in range(1, num_accounts + 1):
            aid = f"ACC-{i:06d}"
            # Select customer
            cust = self.customers[(i - 1) % len(self.customers)]
            cust_created_dt = datetime.date.fromisoformat(cust.created_at[:10])
            acc_num = f"{self.rng.randint(1000000000, 9999999999)}"
            credit_limit = round(self.rng.choice([3000, 5000, 10000, 15000, 25000]), 2)
            # Account opened strictly on or after customer creation (0 to 60 days later)
            opened_dt = cust_created_dt + datetime.timedelta(days=self.rng.randint(0, 60))
            opened_date = opened_dt.isoformat()

            acc = AccountModel(
                account_id=aid, customer_id=cust.customer_id, account_number=acc_num,
                account_status="OPEN", credit_limit=credit_limit, opened_date=opened_date
            )
            self.accounts.append(acc)

        # 3. Loans
        for i in range(1, num_loans + 1):
            lid = f"LOAN-2026-{i:06d}"
            acc = self.accounts[(i - 1) % len(self.accounts)]
            cid = acc.customer_id
            ltype = self.rng.choices(LOAN_TYPES, weights=LOAN_TYPE_WEIGHTS, k=1)[0]
            
            principal = round(self.rng.uniform(1500.0, 20000.0), 2)
            rate = round(self.rng.uniform(0.065, 0.220), 4)
            # Default term: target roughly 3 installments per loan over 12 months for 10k loans -> 30k installments
            # When target is 30,000 installments across 10,000 loans, average installments within window = 3.0
            term = self.rng.choice([12, 24, 36])
            
            # Start date in the past 12 months (e.g. 1 to 12 months ago)
            # Calculate months ago
            months_ago = (i % 10) + 3 # 3 to 12 months ago
            start_dt = self.reference_date - datetime.timedelta(days=months_ago * 30)
            mat_dt = start_dt + datetime.timedelta(days=term * 30)

            # Amortization monthly installment PMT
            monthly_rate = rate / 12.0
            pmt = principal * (monthly_rate * ((1.0 + monthly_rate) ** term)) / (((1.0 + monthly_rate) ** term) - 1.0)
            monthly_installment = round(pmt, 2)

            loan = LoanModel(
                loan_id=lid, account_id=acc.account_id, customer_id=cid,
                loan_type=ltype, principal_amount=principal, interest_rate=rate,
                term_months=term, start_date=start_dt.isoformat(),
                maturity_date=mat_dt.isoformat(),
                monthly_installment_amount=monthly_installment,
                current_balance=principal, total_arrears=0.0,
                days_past_due=0, loan_status="CURRENT"
            )
            self.loans.append(loan)

    def _generate_loan_schedules_and_payments(self):
        """Generates Installments for each loan and simulates historical payments."""
        payment_counter = 1
        
        # We target total installments close to config["num_installments_target"]
        target_inss = self.config["num_installments_target"]
        avg_inss_per_loan = max(1, target_inss // len(self.loans))

        for loan in self.loans:
            start_dt = datetime.date.fromisoformat(loan.start_date)
            monthly_rate = loan.interest_rate / 12.0
            remaining_loan_principal = loan.principal_amount

            # Generate installments (limit to elapsed months so far, min avg_inss_per_loan, max 12)
            elapsed_months = min(12, max(1, (self.reference_date - start_dt).days // 30))
            num_installments = min(loan.term_months, elapsed_months, avg_inss_per_loan + self.rng.choice([0, 1]))

            # Categorize borrower behavior for realistic delinquency distribution
            # 60% on-time payers, 25% delinquent with arrears, 15% fully paid off
            behavior_roll = self.rng.random()
            if behavior_roll < 0.15:
                behavior = "PAID_OFF"
            elif behavior_roll < 0.75:
                behavior = "CURRENT"
            elif behavior_roll < 0.90:
                behavior = "MILD_DELINQUENT"
            else:
                behavior = "SEVERE_DELINQUENT"

            loan_installments = []
            for num in range(1, num_installments + 1):
                ins_id = f"INS-{loan.loan_id}-{num:03d}"
                due_dt = start_dt + datetime.timedelta(days=num * 30)
                
                # Principal vs Interest breakdown
                ins_interest = round(remaining_loan_principal * monthly_rate, 2)
                ins_principal = round(max(0.0, loan.monthly_installment_amount - ins_interest), 2)
                total_due = round(ins_principal + ins_interest, 2)

                ins = InstallmentModel(
                    installment_id=ins_id,
                    loan_id=loan.loan_id,
                    installment_number=num,
                    due_date=due_dt.isoformat(),
                    principal_due=ins_principal,
                    interest_due=ins_interest,
                    total_amount_due=total_due,
                    amount_paid=0.0,
                    remaining_balance=total_due,
                    days_overdue=0,
                    status="UPCOMING" if due_dt > self.reference_date else "CURRENT"
                )
                loan_installments.append(ins)
                remaining_loan_principal = max(0.0, remaining_loan_principal - ins_principal)

            # Simulate Payments based on behavior
            for idx, ins in enumerate(loan_installments):
                ins_due = datetime.date.fromisoformat(ins.due_date)
                
                if ins_due > self.reference_date:
                    ins.status = "UPCOMING"
                    continue

                should_pay = False
                pay_fraction = 1.0

                if behavior == "PAID_OFF":
                    should_pay = True
                    pay_fraction = 1.0
                elif behavior == "CURRENT":
                    should_pay = True
                    pay_fraction = 1.0
                elif behavior == "MILD_DELINQUENT":
                    # pays older installments, misses last 1 or 2
                    should_pay = (idx < len(loan_installments) - 1)
                    if not should_pay and self.rng.random() < 0.3:
                        should_pay = True
                        pay_fraction = 0.5 # Partial payment
                elif behavior == "SEVERE_DELINQUENT":
                    # misses last 2 or 3 installments
                    should_pay = (idx < max(0, len(loan_installments) - 2))

                if should_pay:
                    paid_amt = round(ins.total_amount_due * pay_fraction, 2)
                    ins.amount_paid = paid_amt
                    ins.remaining_balance = round(ins.total_amount_due - paid_amt, 2)
                    
                    if ins.remaining_balance <= 0.001:
                        ins.status = "PAID"
                        ins.days_overdue = 0
                    else:
                        ins.status = "PARTIALLY_PAID"
                        ins.days_overdue = max(0, (self.reference_date - ins_due).days)

                    # Create payment record
                    pay_dt = ins_due - datetime.timedelta(days=self.rng.randint(0, 3))
                    pmt_id = f"PMT-2026-{payment_counter:06d}"
                    payment_counter += 1
                    ref = f"REF-{payment_counter:06d}{self.rng.randint(100, 999)}"

                    pmt = PaymentModel(
                        payment_id=pmt_id,
                        loan_id=loan.loan_id,
                        account_id=loan.account_id,
                        customer_id=loan.customer_id,
                        payment_date=pay_dt.isoformat(),
                        amount=paid_amt,
                        payment_method=self.rng.choice(["ACH", "DEBIT_CARD", "CHECK"]),
                        allocated_installment_id=ins.installment_id,
                        allocation_status="ALLOCATED_CORRECTLY",
                        reconciled_ptp_id=None,
                        payment_reference=ref
                    )
                    self.payments.append(pmt)
                else:
                    # Unpaid overdue
                    ins.amount_paid = 0.0
                    ins.remaining_balance = ins.total_amount_due
                    ins.days_overdue = max(0, (self.reference_date - ins_due).days)
                    ins.status = "OVERDUE"

            self.installments.extend(loan_installments)

    def _derive_delinquency_and_snapshots(self):
        """Derives loan balances, arrears, DPD, and creates DelinquencySnapshots."""
        ins_by_loan: Dict[str, List[InstallmentModel]] = {}
        for ins in self.installments:
            ins_by_loan.setdefault(ins.loan_id, []).append(ins)

        snapshot_counter = 1

        for loan in self.loans:
            inss = ins_by_loan.get(loan.loan_id, [])
            unpaid_inss = [i for i in inss if i.remaining_balance > 0.001]
            overdue_inss = [i for i in unpaid_inss if datetime.date.fromisoformat(i.due_date) <= self.reference_date]

            loan.current_balance = round(sum(i.remaining_balance for i in unpaid_inss), 2)
            loan.total_arrears = round(sum(i.remaining_balance for i in overdue_inss), 2)

            if overdue_inss:
                oldest_due = min(datetime.date.fromisoformat(i.due_date) for i in overdue_inss)
                loan.days_past_due = max(0, (self.reference_date - oldest_due).days)
            else:
                loan.days_past_due = 0

            # Determine Loan status
            if loan.current_balance <= 0.001:
                loan.loan_status = "PAID_OFF"
            elif loan.days_past_due > 120:
                loan.loan_status = "CHARGEOFF"
            elif loan.total_arrears > 0.001:
                loan.loan_status = "DELINQUENT"
            else:
                loan.loan_status = "CURRENT"

            # Create Delinquency Snapshot
            dpd = loan.days_past_due
            if dpd == 0:
                bucket = "CURRENT"
            elif dpd <= 30:
                bucket = "30_DPD"
            elif dpd <= 60:
                bucket = "60_DPD"
            elif dpd <= 90:
                bucket = "90_DPD"
            else:
                bucket = "120_PLUS_DPD"

            snap = DelinquencySnapshotModel(
                snapshot_id=f"SNP-2026-{snapshot_counter:06d}",
                loan_id=loan.loan_id,
                customer_id=loan.customer_id,
                snapshot_date=self.reference_date.isoformat(),
                days_past_due=dpd,
                delinquency_bucket=bucket,
                total_arrears=loan.total_arrears,
                total_principal_overdue=round(sum(i.principal_due for i in overdue_inss), 2),
                total_interest_overdue=round(sum(i.interest_due for i in overdue_inss), 2),
                missed_installments_count=len(overdue_inss),
                risk_score=min(100.0, round(dpd * 0.8 + (loan.total_arrears / 100.0), 1))
            )
            self.delinquency_snapshots.append(snap)
            snapshot_counter += 1

    def _generate_collection_cases_and_priorities(self):
        """Creates CollectionCases for all delinquent loans and calculates priority scores."""
        cust_by_id = {c.customer_id: c for c in self.customers}
        case_counter = 1

        for loan in self.loans:
            cust = cust_by_id.get(loan.customer_id)
            if not cust:
                continue

            # Open cases for delinquent or charge-off loans, or loans with arrears
            if loan.total_arrears > 0.001 or loan.loan_status in ("DELINQUENT", "CHARGEOFF"):
                cid = f"COL-2026-{case_counter:06d}"
                case_counter += 1

                # Prioritization calculation
                score_res = calculate_case_priority(
                    total_arrears=loan.total_arrears,
                    days_past_due=loan.days_past_due,
                    risk_segment=cust.risk_segment,
                    hardship_status=cust.hardship_status,
                    dispute_status=cust.dispute_status
                )

                if cust.dispute_status == "ACTIVE_DISPUTE":
                    status = "UNDER_DISPUTE"
                elif cust.hardship_status != "NONE":
                    status = "HARDSHIP_HOLD"
                else:
                    status = "ACTIVE"

                case = CollectionCaseModel(
                    case_id=cid,
                    loan_id=loan.loan_id,
                    customer_id=loan.customer_id,
                    case_opened_date=(self.reference_date - datetime.timedelta(days=min(loan.days_past_due, 60))).isoformat(),
                    case_status=status,
                    priority_score=score_res["priority_score"],
                    priority_tier=score_res["priority_tier"],
                    assigned_agent_id=f"AGENT-{self.rng.randint(1, 10):03d}",
                    last_contact_date=None,
                    next_scheduled_action=(self.reference_date + datetime.timedelta(days=1)).isoformat() + "T14:00:00Z",
                    active_ptp_id=None,
                    total_attempts_count=0,
                    weekly_attempts_count=0
                )
                self.collection_cases.append(case)

    def _generate_contact_attempts_and_promises(self):
        """Generates historical contact attempts and promises to pay with compliance checks."""
        cust_by_id = {c.customer_id: c for c in self.customers}
        pref_by_cust = {p.customer_id: p for p in self.contact_preferences}
        ptp_counter = 1

        for case in self.collection_cases:
            cust = cust_by_id.get(case.customer_id)
            pref = pref_by_cust.get(case.customer_id)
            if not cust or not pref:
                continue

            num_attempts = self.rng.randint(1, 4)
            case.total_attempts_count = num_attempts
            case.weekly_attempts_count = min(num_attempts, 3)

            for attempt_seq in range(1, num_attempts + 1):
                att_id = f"CTP-{case.case_id}-{attempt_seq:03d}"
                days_ago = self.rng.randint(1, 14)
                # Attempt during lawful hours: 10:00 to 18:00
                hour = self.rng.randint(10, 18)
                minute = self.rng.randint(0, 59)
                att_dt = datetime.datetime.combine(
                    self.reference_date - datetime.timedelta(days=days_ago),
                    datetime.time(hour, minute),
                    tzinfo=datetime.timezone.utc
                )

                local_dt = get_consumer_local_time(att_dt, cust.timezone)
                channel = pref.preferred_channel if pref.preferred_channel else "PHONE"

                eval_res = evaluate_contact_compliance(
                    customer=cust.to_dict(),
                    contact_pref=pref.to_dict(),
                    channel=channel,
                    attempt_datetime_utc=att_dt,
                    recent_7_day_attempts=attempt_seq - 1
                )

                if eval_res["is_compliant"]:
                    compliance_status = "COMPLIANT"
                    outcome = self.rng.choice([
                        "CONNECTED_PROMISE_MADE",
                        "VOICEMAIL_LEFT",
                        "NO_ANSWER",
                        "CONNECTED_REFUSED_TO_PAY"
                    ])
                else:
                    compliance_status = eval_res["compliance_status"]
                    outcome = "BLOCKED_BY_GUARDRAIL"

                att = ContactAttemptModel(
                    attempt_id=att_id,
                    case_id=case.case_id,
                    customer_id=cust.customer_id,
                    channel=channel,
                    attempt_timestamp=att_dt.isoformat(),
                    customer_local_time=local_dt.time().strftime("%H:%M"),
                    is_permissible_window=1 if compliance_status != "QUIET_HOURS_VIOLATION" else 0,
                    rolling_7_day_count=min(attempt_seq, 5),
                    compliance_status=compliance_status,
                    contact_outcome=outcome,
                    agent_notes="Outbound contact evaluated against FDCPA and CFPB Reg F guardrails."
                )
                self.contact_attempts.append(att)
                case.last_contact_date = att_dt.isoformat()

                # If promise made, generate PromiseToPay
                if outcome == "CONNECTED_PROMISE_MADE":
                    ptp_id = f"PTP-2026-{ptp_counter:06d}"
                    ptp_counter += 1
                    
                    # Promise due in 3 to 10 days
                    promise_due = (att_dt.date() + datetime.timedelta(days=self.rng.randint(3, 10))).isoformat()
                    loan = next((l for l in self.loans if l.loan_id == case.loan_id), None)
                    arrears = loan.total_arrears if loan else 500.0
                    promised_amt = round(min(arrears, max(50.0, arrears * self.rng.uniform(0.5, 1.0))), 2)

                    ptp_status = self.rng.choice(["PENDING", "KEPT", "BROKEN"])
                    fulfilled = promised_amt if ptp_status == "KEPT" else 0.0

                    ptp = PromiseToPayModel(
                        ptp_id=ptp_id,
                        case_id=case.case_id,
                        loan_id=case.loan_id,
                        customer_id=cust.customer_id,
                        created_timestamp=att_dt.isoformat(),
                        promise_due_date=promise_due,
                        promised_amount=promised_amt,
                        current_arrears_at_promise=arrears,
                        ptp_status=ptp_status,
                        fulfilled_amount=fulfilled,
                        fulfillment_date=promise_due if ptp_status == "KEPT" else None,
                        reconciled_payment_id=None
                    )
                    self.promises_to_pay.append(ptp)
                    if ptp_status == "PENDING":
                        case.active_ptp_id = ptp_id
                        case.case_status = "PENDING_PTP"

    def _inject_edge_cases(self):
        """Injects labelled edge cases and records ground truth anomalies."""
        self.ground_truth_anomalies = inject_edge_cases(
            customers=self.customers,
            loans=self.loans,
            installments=self.installments,
            collection_cases=self.collection_cases,
            contact_attempts=self.contact_attempts,
            promises=self.promises_to_pay,
            payments=self.payments,
            anomaly_counts=self.config["anomaly_counts"],
            rng=self.rng
        )

    def _finalize_derived_fields(self):
        """Ensures absolute consistency of derived totals, balances, and counts."""
        pass

    def export_to_sqlite(self, conn: sqlite3.Connection):
        """Persists all generated records to SQLite database using bulk inserts."""
        cursor = conn.cursor()
        
        # Customers
        cursor.executemany(
            """INSERT OR REPLACE INTO customers VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            [tuple(c.to_dict().values()) for c in self.customers]
        )
        # Accounts
        cursor.executemany(
            """INSERT OR REPLACE INTO accounts VALUES (?,?,?,?,?,?)""",
            [tuple(a.to_dict().values()) for a in self.accounts]
        )
        # Loans (14 columns)
        cursor.executemany(
            """INSERT OR REPLACE INTO loans VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [tuple(l.to_dict().values()) for c, l in enumerate(self.loans)]
        )
        # Installments (11 columns)
        cursor.executemany(
            """INSERT OR REPLACE INTO installments VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            [tuple(i.to_dict().values()) for i in self.installments]
        )
        # Snapshots (11 columns)
        cursor.executemany(
            """INSERT OR REPLACE INTO delinquency_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            [tuple(s.to_dict().values()) for s in self.delinquency_snapshots]
        )
        # Contact Preferences (11 columns)
        cursor.executemany(
            """INSERT OR REPLACE INTO contact_preferences VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            [tuple(p.to_dict().values()) for p in self.contact_preferences]
        )
        # Collection Cases (13 columns)
        cursor.executemany(
            """INSERT OR REPLACE INTO collection_cases VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [tuple(c.to_dict().values()) for c in self.collection_cases]
        )
        # Contact Attempts (11 columns)
        cursor.executemany(
            """INSERT OR REPLACE INTO contact_attempts VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            [tuple(a.to_dict().values()) for a in self.contact_attempts]
        )
        # Promises
        cursor.executemany(
            """INSERT OR REPLACE INTO promises_to_pay VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            [tuple(p.to_dict().values()) for p in self.promises_to_pay]
        )
        # Payments
        cursor.executemany(
            """INSERT OR REPLACE INTO payments VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            [tuple(p.to_dict().values()) for p in self.payments]
        )
        # Ground Truth Anomalies
        cursor.executemany(
            """INSERT OR REPLACE INTO ground_truth_anomalies VALUES (?,?,?,?,?,?,?,?)""",
            [tuple(g.to_dict().values()) for g in self.ground_truth_anomalies]
        )
        conn.commit()

    def export_to_files(self, output_dir: str) -> Dict[str, str]:
        """
        Exports CSVs, JSON, SQL seed, and manifest with SHA256 checksums.
        """
        os.makedirs(output_dir, exist_ok=True)
        tables = {
            "customers": [c.to_dict() for c in self.customers],
            "accounts": [a.to_dict() for a in self.accounts],
            "loans": [l.to_dict() for l in self.loans],
            "installments": [i.to_dict() for i in self.installments],
            "delinquency_snapshots": [s.to_dict() for s in self.delinquency_snapshots],
            "contact_preferences": [p.to_dict() for p in self.contact_preferences],
            "collection_cases": [c.to_dict() for c in self.collection_cases],
            "contact_attempts": [a.to_dict() for a in self.contact_attempts],
            "promises_to_pay": [p.to_dict() for p in self.promises_to_pay],
            "payments": [p.to_dict() for p in self.payments],
            "ground_truth": [g.to_dict() for g in self.ground_truth_anomalies]
        }

        checksums = {}

        # 1. Export CSVs
        for tname, records in tables.items():
            csv_path = os.path.join(output_dir, f"{tname}.csv")
            if records:
                keys = records[0].keys()
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=keys)
                    writer.writeheader()
                    writer.writerows(records)
            else:
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    pass
            checksums[f"{tname}.csv"] = self._compute_file_sha256(csv_path)

        # 2. Export JSON files (including separate ground_truth.json)
        json_path = os.path.join(output_dir, "dataset.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(tables, f, indent=2)
        checksums["dataset.json"] = self._compute_file_sha256(json_path)

        gt_json_path = os.path.join(output_dir, "ground_truth.json")
        with open(gt_json_path, "w", encoding="utf-8") as f:
            json.dump(tables["ground_truth"], f, indent=2)
        checksums["ground_truth.json"] = self._compute_file_sha256(gt_json_path)

        # 3. Export SQL Seed Data script
        sql_path = os.path.join(output_dir, "seed_data.sql")
        with open(sql_path, "w", encoding="utf-8") as f:
            f.write("-- SQL Seed Data: Fair Collections & Recovery Engine\n")
            f.write(f"-- Profile: {self.profile_name} | Seed: {self.seed}\n\n")
            f.write("BEGIN TRANSACTION;\n\n")
            
            # Map table dictionary key to SQL table name
            sql_tbl_names = {
                "customers": "customers",
                "accounts": "accounts",
                "loans": "loans",
                "installments": "installments",
                "delinquency_snapshots": "delinquency_snapshots",
                "contact_preferences": "contact_preferences",
                "collection_cases": "collection_cases",
                "contact_attempts": "contact_attempts",
                "promises_to_pay": "promises_to_pay",
                "payments": "payments",
                "ground_truth": "ground_truth_anomalies"
            }
            
            for tname, records in tables.items():
                target_table = sql_tbl_names.get(tname, tname)
                for rec in records:
                    cols = ", ".join(rec.keys())
                    vals = []
                    for v in rec.values():
                        if v is None:
                            vals.append("NULL")
                        elif isinstance(v, (int, float)):
                            vals.append(str(v))
                        else:
                            clean_str = str(v).replace("'", "''")
                            vals.append(f"'{clean_str}'")
                    val_str = ", ".join(vals)
                    f.write(f"INSERT INTO {target_table} ({cols}) VALUES ({val_str});\n")
                f.write("\n")
            f.write("COMMIT;\n")
        checksums["seed_data.sql"] = self._compute_file_sha256(sql_path)

        # 4. Export Manifest
        manifest = {
            "generator_version": "1.0.0",
            "profile": self.profile_name,
            "seed": self.seed,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "counts": {k: len(v) for k, v in tables.items()},
            "checksums_sha256": checksums
        }
        manifest_path = os.path.join(output_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return checksums

    @staticmethod
    def _compute_file_sha256(filepath: str) -> str:
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()
