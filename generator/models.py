"""
Data Models for Synthetic Data Generation and Schema Validation.
"""

from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any


@dataclass
class CustomerModel:
    customer_id: str
    first_name: str
    last_name: str
    email: str
    phone_number: str
    timezone: str
    risk_segment: str
    hardship_status: str
    dispute_status: str
    cease_desist_flag: int
    attorney_represented: int
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AccountModel:
    account_id: str
    customer_id: str
    account_number: str
    account_status: str
    credit_limit: float
    opened_date: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LoanModel:
    loan_id: str
    account_id: str
    customer_id: str
    loan_type: str
    principal_amount: float
    interest_rate: float
    term_months: int
    start_date: str
    maturity_date: str
    monthly_installment_amount: float
    current_balance: float
    total_arrears: float
    days_past_due: int
    loan_status: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InstallmentModel:
    installment_id: str
    loan_id: str
    installment_number: int
    due_date: str
    principal_due: float
    interest_due: float
    total_amount_due: float
    amount_paid: float
    remaining_balance: float
    days_overdue: int
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DelinquencySnapshotModel:
    snapshot_id: str
    loan_id: str
    customer_id: str
    snapshot_date: str
    days_past_due: int
    delinquency_bucket: str
    total_arrears: float
    total_principal_overdue: float
    total_interest_overdue: float
    missed_installments_count: int
    risk_score: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ContactPreferenceModel:
    preference_id: str
    customer_id: str
    preferred_channel: str
    opt_in_phone: int
    opt_in_sms: int
    opt_in_email: int
    permissible_start_time: str
    permissible_end_time: str
    do_not_call_employer: int
    allowed_contact_days: str
    last_consent_update: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CollectionCaseModel:
    case_id: str
    loan_id: str
    customer_id: str
    case_opened_date: str
    case_status: str
    priority_score: float
    priority_tier: str
    assigned_agent_id: Optional[str]
    last_contact_date: Optional[str]
    next_scheduled_action: Optional[str]
    active_ptp_id: Optional[str]
    total_attempts_count: int
    weekly_attempts_count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ContactAttemptModel:
    attempt_id: str
    case_id: str
    customer_id: str
    channel: str
    attempt_timestamp: str
    customer_local_time: str
    is_permissible_window: int
    rolling_7_day_count: int
    compliance_status: str
    contact_outcome: str
    agent_notes: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PromiseToPayModel:
    ptp_id: str
    case_id: str
    loan_id: str
    customer_id: str
    created_timestamp: str
    promise_due_date: str
    promised_amount: float
    current_arrears_at_promise: float
    ptp_status: str
    fulfilled_amount: float
    fulfillment_date: Optional[str]
    reconciled_payment_id: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PaymentModel:
    payment_id: str
    loan_id: str
    account_id: str
    customer_id: str
    payment_date: str
    amount: float
    payment_method: str
    allocated_installment_id: str
    allocation_status: str
    reconciled_ptp_id: Optional[str]
    payment_reference: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GroundTruthAnomalyModel:
    anomaly_id: str
    entity_type: str
    entity_id: str
    issue_type: str
    description: str
    expected_decision: str
    detection_rule: str
    severity: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
