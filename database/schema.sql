-- Database Schema: Fair Collections & Recovery Workflow Engine
-- Dialect: SQLite 3 / Standard ANSI SQL with Foreign Key Enforcement

PRAGMA foreign_keys = ON;

-- 1. Customers Table
CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone_number TEXT NOT NULL UNIQUE,
    timezone TEXT NOT NULL CHECK (timezone IN ('America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles')),
    risk_segment TEXT NOT NULL CHECK (risk_segment IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    hardship_status TEXT NOT NULL CHECK (hardship_status IN ('NONE', 'TEMPORARY_UNEMPLOYMENT', 'MEDICAL_EMERGENCY', 'NATURAL_DISASTER')),
    dispute_status TEXT NOT NULL CHECK (dispute_status IN ('NONE', 'ACTIVE_DISPUTE', 'RESOLVED')),
    cease_desist_flag INTEGER NOT NULL DEFAULT 0 CHECK (cease_desist_flag IN (0, 1)),
    attorney_represented INTEGER NOT NULL DEFAULT 0 CHECK (attorney_represented IN (0, 1)),
    created_at TEXT NOT NULL
);

-- 2. Accounts Table
CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    account_number TEXT NOT NULL UNIQUE,
    account_status TEXT NOT NULL CHECK (account_status IN ('OPEN', 'DELINQUENT', 'SUSPENDED', 'CLOSED')),
    credit_limit REAL NOT NULL CHECK (credit_limit >= 0.0),
    opened_date TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE RESTRICT
);

-- 3. Loans Table
CREATE TABLE IF NOT EXISTS loans (
    loan_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    loan_type TEXT NOT NULL CHECK (loan_type IN ('PERSONAL', 'AUTO', 'MORTGAGE', 'SME_REVOLVING')),
    principal_amount REAL NOT NULL CHECK (principal_amount > 0.0),
    interest_rate REAL NOT NULL CHECK (interest_rate > 0.0 AND interest_rate < 1.0),
    term_months INTEGER NOT NULL CHECK (term_months IN (12, 24, 36)),
    start_date TEXT NOT NULL,
    maturity_date TEXT NOT NULL,
    monthly_installment_amount REAL NOT NULL CHECK (monthly_installment_amount > 0.0),
    current_balance REAL NOT NULL CHECK (current_balance >= 0.0),
    total_arrears REAL NOT NULL CHECK (total_arrears >= 0.0),
    days_past_due INTEGER NOT NULL CHECK (days_past_due >= 0),
    loan_status TEXT NOT NULL CHECK (loan_status IN ('CURRENT', 'DELINQUENT', 'PAID_OFF', 'CHARGEOFF')),
    FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE RESTRICT,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE RESTRICT
);

-- 4. Installments Table
CREATE TABLE IF NOT EXISTS installments (
    installment_id TEXT PRIMARY KEY,
    loan_id TEXT NOT NULL,
    installment_number INTEGER NOT NULL CHECK (installment_number >= 1),
    due_date TEXT NOT NULL,
    principal_due REAL NOT NULL CHECK (principal_due >= 0.0),
    interest_due REAL NOT NULL CHECK (interest_due >= 0.0),
    total_amount_due REAL NOT NULL CHECK (total_amount_due >= 0.0),
    amount_paid REAL NOT NULL DEFAULT 0.0 CHECK (amount_paid >= 0.0),
    remaining_balance REAL NOT NULL CHECK (remaining_balance >= 0.0),
    days_overdue INTEGER NOT NULL DEFAULT 0 CHECK (days_overdue >= 0),
    status TEXT NOT NULL CHECK (status IN ('UPCOMING', 'CURRENT', 'OVERDUE', 'PAID', 'PARTIALLY_PAID')),
    FOREIGN KEY (loan_id) REFERENCES loans(loan_id) ON DELETE RESTRICT
);

-- 5. Delinquency Snapshots Table
CREATE TABLE IF NOT EXISTS delinquency_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    loan_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    days_past_due INTEGER NOT NULL CHECK (days_past_due >= 0),
    delinquency_bucket TEXT NOT NULL CHECK (delinquency_bucket IN ('CURRENT', '30_DPD', '60_DPD', '90_DPD', '120_PLUS_DPD')),
    total_arrears REAL NOT NULL CHECK (total_arrears >= 0.0),
    total_principal_overdue REAL NOT NULL CHECK (total_principal_overdue >= 0.0),
    total_interest_overdue REAL NOT NULL CHECK (total_interest_overdue >= 0.0),
    missed_installments_count INTEGER NOT NULL CHECK (missed_installments_count >= 0),
    risk_score REAL NOT NULL CHECK (risk_score >= 0.0 AND risk_score <= 100.0),
    FOREIGN KEY (loan_id) REFERENCES loans(loan_id) ON DELETE RESTRICT,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE RESTRICT
);

-- 6. Contact Preferences Table
CREATE TABLE IF NOT EXISTS contact_preferences (
    preference_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL UNIQUE,
    preferred_channel TEXT NOT NULL CHECK (preferred_channel IN ('PHONE', 'SMS', 'EMAIL', 'PORTAL')),
    opt_in_phone INTEGER NOT NULL DEFAULT 1 CHECK (opt_in_phone IN (0, 1)),
    opt_in_sms INTEGER NOT NULL DEFAULT 1 CHECK (opt_in_sms IN (0, 1)),
    opt_in_email INTEGER NOT NULL DEFAULT 1 CHECK (opt_in_email IN (0, 1)),
    permissible_start_time TEXT NOT NULL DEFAULT '08:00',
    permissible_end_time TEXT NOT NULL DEFAULT '21:00',
    do_not_call_employer INTEGER NOT NULL DEFAULT 1 CHECK (do_not_call_employer IN (0, 1)),
    allowed_contact_days TEXT NOT NULL DEFAULT 'MON,TUE,WED,THU,FRI,SAT',
    last_consent_update TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE
);

-- 7. Collection Cases Table
CREATE TABLE IF NOT EXISTS collection_cases (
    case_id TEXT PRIMARY KEY,
    loan_id TEXT NOT NULL UNIQUE,
    customer_id TEXT NOT NULL,
    case_opened_date TEXT NOT NULL,
    case_status TEXT NOT NULL CHECK (case_status IN ('ACTIVE', 'PENDING_PTP', 'UNDER_DISPUTE', 'HARDSHIP_HOLD', 'RESOLVED', 'CLOSED_PAID')),
    priority_score REAL NOT NULL CHECK (priority_score >= 0.0 AND priority_score <= 100.0),
    priority_tier TEXT NOT NULL CHECK (priority_tier IN ('P1_CRITICAL', 'P2_HIGH', 'P3_MEDIUM', 'P4_LOW')),
    assigned_agent_id TEXT,
    last_contact_date TEXT,
    next_scheduled_action TEXT,
    active_ptp_id TEXT,
    total_attempts_count INTEGER NOT NULL DEFAULT 0 CHECK (total_attempts_count >= 0),
    weekly_attempts_count INTEGER NOT NULL DEFAULT 0 CHECK (weekly_attempts_count >= 0),
    FOREIGN KEY (loan_id) REFERENCES loans(loan_id) ON DELETE RESTRICT,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE RESTRICT
);

-- 8. Contact Attempts Table
CREATE TABLE IF NOT EXISTS contact_attempts (
    attempt_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    channel TEXT NOT NULL CHECK (channel IN ('PHONE', 'SMS', 'EMAIL', 'LETTER', 'PORTAL')),
    attempt_timestamp TEXT NOT NULL,
    customer_local_time TEXT NOT NULL,
    is_permissible_window INTEGER NOT NULL CHECK (is_permissible_window IN (0, 1)),
    rolling_7_day_count INTEGER NOT NULL CHECK (rolling_7_day_count >= 0),
    compliance_status TEXT NOT NULL CHECK (compliance_status IN (
        'COMPLIANT',
        'QUIET_HOURS_VIOLATION',
        'FREQUENCY_CAP_EXCEEDED',
        'DISPUTE_HOLD_VIOLATION',
        'HARDSHIP_HOLD_VIOLATION',
        'CEASE_DESIST_VIOLATION',
        'BLOCKED_BY_GUARDRAIL'
    )),
    contact_outcome TEXT NOT NULL CHECK (contact_outcome IN (
        'CONNECTED_PROMISE_MADE',
        'CONNECTED_REFUSED_TO_PAY',
        'CONNECTED_HARDSHIP_CLAIMED',
        'CONNECTED_DISPUTED_DEBT',
        'VOICEMAIL_LEFT',
        'NO_ANSWER',
        'EMAIL_SENT',
        'SMS_DELIVERED',
        'BLOCKED_BY_GUARDRAIL'
    )),
    agent_notes TEXT,
    FOREIGN KEY (case_id) REFERENCES collection_cases(case_id) ON DELETE RESTRICT,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE RESTRICT
);

-- 9. Promises To Pay Table
CREATE TABLE IF NOT EXISTS promises_to_pay (
    ptp_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    loan_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    created_timestamp TEXT NOT NULL,
    promise_due_date TEXT NOT NULL,
    promised_amount REAL NOT NULL CHECK (promised_amount > 0.0),
    current_arrears_at_promise REAL NOT NULL CHECK (current_arrears_at_promise >= 0.0),
    ptp_status TEXT NOT NULL CHECK (ptp_status IN ('PENDING', 'KEPT', 'PARTIALLY_KEPT', 'BROKEN', 'CANCELLED')),
    fulfilled_amount REAL NOT NULL DEFAULT 0.0 CHECK (fulfilled_amount >= 0.0),
    fulfillment_date TEXT,
    reconciled_payment_id TEXT,
    FOREIGN KEY (case_id) REFERENCES collection_cases(case_id) ON DELETE RESTRICT,
    FOREIGN KEY (loan_id) REFERENCES loans(loan_id) ON DELETE RESTRICT,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE RESTRICT
);

-- 10. Payments Table
CREATE TABLE IF NOT EXISTS payments (
    payment_id TEXT PRIMARY KEY,
    loan_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    payment_date TEXT NOT NULL,
    amount REAL NOT NULL CHECK (amount > 0.0),
    payment_method TEXT NOT NULL CHECK (payment_method IN ('ACH', 'DEBIT_CARD', 'WIRE', 'CHECK')),
    allocated_installment_id TEXT NOT NULL,
    allocation_status TEXT NOT NULL CHECK (allocation_status IN ('ALLOCATED_CORRECTLY', 'MISALLOCATED_WRONG_INSTALLMENT')),
    reconciled_ptp_id TEXT,
    payment_reference TEXT NOT NULL UNIQUE,
    FOREIGN KEY (loan_id) REFERENCES loans(loan_id) ON DELETE RESTRICT,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE RESTRICT,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE RESTRICT,
    FOREIGN KEY (allocated_installment_id) REFERENCES installments(installment_id) ON DELETE RESTRICT
);

-- 11. Ground Truth Anomalies Table (Preserved separately for audit/testing)
CREATE TABLE IF NOT EXISTS ground_truth_anomalies (
    anomaly_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    issue_type TEXT NOT NULL CHECK (issue_type IN (
        'PAID_ACCOUNT_REMAINS_IN_COLLECTION',
        'CONTACT_OUTSIDE_ALLOWED_WINDOW',
        'PAYMENT_ALLOCATED_TO_WRONG_INSTALLMENT',
        'PROMISE_AMOUNT_EXCEEDS_ARREARS',
        'DISPUTED_DEBT_TREATED_AS_CONFIRMED'
    )),
    description TEXT NOT NULL,
    expected_decision TEXT NOT NULL,
    detection_rule TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('CRITICAL', 'HIGH', 'MEDIUM'))
);

-- 12. Audit Events Table (Traceability & Immutable History)
CREATE TABLE IF NOT EXISTS audit_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_timestamp TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor_persona TEXT NOT NULL CHECK (actor_persona IN ('SYSTEM', 'ANALYST', 'REVIEWER', 'CUSTOMER', 'ADMIN')),
    actor_id TEXT NOT NULL,
    previous_state TEXT,
    new_state TEXT,
    notes TEXT
);

-- Indexes for Fast Querying and Relational Integrity
CREATE INDEX IF NOT EXISTS idx_accounts_customer ON accounts(customer_id);
CREATE INDEX IF NOT EXISTS idx_loans_customer ON loans(customer_id);
CREATE INDEX IF NOT EXISTS idx_loans_account ON loans(account_id);
CREATE INDEX IF NOT EXISTS idx_installments_loan ON installments(loan_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_loan ON delinquency_snapshots(loan_id);
CREATE INDEX IF NOT EXISTS idx_cases_loan ON collection_cases(loan_id);
CREATE INDEX IF NOT EXISTS idx_cases_priority ON collection_cases(priority_tier, priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_attempts_case ON contact_attempts(case_id);
CREATE INDEX IF NOT EXISTS idx_ptp_case ON promises_to_pay(case_id);
CREATE INDEX IF NOT EXISTS idx_payments_loan ON payments(loan_id);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_events(entity_name, entity_id);
