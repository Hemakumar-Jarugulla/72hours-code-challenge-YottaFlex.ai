# Comprehensive Data Dictionary: Fair Collections & Recovery Engine

This document defines the schema, data types, constraints, validation rules, and cardinalities for the end-to-end fair collection and recovery system.

---

## Entity Relationship Overview & Cardinalities

```
[Customer] (1) <──── (N) [Account] (1) <──── (N) [Loan] (1) <──── (N) [Installment]
   │                       │                    │
   │ (1)                   │ (1)                │ (1)
   ▼                       ▼                    ▼
[ContactPreference]   [Payment] (N) <────── [CollectionCase] (1) <──── (N) [ContactAttempt]
   (1:1)                   │ (N)                │ (1)
                           └──────────────────> ▼
                                           [PromiseToPay] (N)
                                                ▲
                                                │ (1)
                                       [DelinquencySnapshot] (N)
```

- **Customer to Account**: 1 : N (One customer can hold multiple credit/loan accounts)
- **Customer to ContactPreference**: 1 : 1 (One unified contact preference and quiet-hours configuration per customer)
- **Account to Loan**: 1 : N (One account can contain one or more active or historical loan facilities)
- **Loan to Installment**: 1 : N (One loan has multiple scheduled amortization installments, e.g. 12 to 36)
- **Loan to DelinquencySnapshot**: 1 : N (Periodic historical snapshots of loan arrears, DPD, and bucket transitions)
- **Loan to CollectionCase**: 1 : 1 (Active delinquency lifecycle case for a delinquent loan)
- **CollectionCase to ContactAttempt**: 1 : N (Audit trail of every outreach attempt, channel, timestamp, and compliance evaluation)
- **CollectionCase to PromiseToPay (PTP)**: 1 : N (Historical and active repayment commitments made by the customer)
- **Loan to Payment**: 1 : N (Repayments received towards the loan balance and installments)
- **PromiseToPay to Payment**: 1 : 1 (Optional reconciliation link between a commitment and the matching payment transaction)

---

## 1. Customer (`Customer`)
Represents the natural person or business borrower holding the accounts.

| Field Name | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule & Foreign Key |
|---|---|---|---|---|---|---|
| `customer_id` | STRING | Required | Pattern: `CUST-[0-9]{6}` | ID string | Unique (PK) | Immutable primary key |
| `first_name` | STRING | Required | Non-empty alphanumeric string (max 50) | None | Non-unique | Valid string, sanitized |
| `last_name` | STRING | Required | Non-empty alphanumeric string (max 50) | None | Non-unique | Valid string, sanitized |
| `email` | STRING | Required | Standard RFC 5322 email regex | Email | Unique | Valid email format |
| `phone_number` | STRING | Required | E.164 format: `+1[2-9][0-9]{9}` | Phone | Unique | Valid US phone number |
| `timezone` | STRING | Required | `America/New_York`, `America/Chicago`, `America/Denver`, `America/Los_Angeles` | IANA TZ | Non-unique | Must be valid US timezone identifier |
| `risk_segment` | STRING | Required | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` | Enum | Non-unique | Credit risk evaluation grade |
| `hardship_status` | STRING | Required | `NONE`, `TEMPORARY_UNEMPLOYMENT`, `MEDICAL_EMERGENCY`, `NATURAL_DISASTER` | Enum | Non-unique | If not `NONE`, triggers collection freeze |
| `dispute_status` | STRING | Required | `NONE`, `ACTIVE_DISPUTE`, `RESOLVED` | Enum | Non-unique | If `ACTIVE_DISPUTE`, FDCPA Section 809 moratorium applies |
| `cease_desist_flag` | BOOLEAN | Required | `0` (False) or `1` (True) | Boolean | Non-unique | If `1`, all outbound contact is strictly blocked |
| `attorney_represented` | BOOLEAN | Required | `0` (False) or `1` (True) | Boolean | Non-unique | If `1`, direct contact with debtor prohibited |
| `created_at` | TIMESTAMP | Required | ISO 8601 (`YYYY-MM-DDTHH:MM:SSZ`) | UTC | Non-unique | Must be <= current timestamp |

---

## 2. Account (`Account`)
Represents the umbrella financial account under which loans are originated.

| Field Name | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule & Foreign Key |
|---|---|---|---|---|---|---|
| `account_id` | STRING | Required | Pattern: `ACC-[0-9]{6}` | ID string | Unique (PK) | Primary key |
| `customer_id` | STRING | Required | Pattern: `CUST-[0-9]{6}` | ID string | Non-unique | Foreign key -> `Customer.customer_id` |
| `account_number` | STRING | Required | 10-digit numeric string | Number | Unique | Format validation `^\d{10}$` |
| `account_status` | STRING | Required | `OPEN`, `DELINQUENT`, `SUSPENDED`, `CLOSED` | Enum | Non-unique | Must reflect loan roll-up status |
| `credit_limit` | FLOAT | Required | Positive float >= 0.00 | USD ($) | Non-unique | Numeric >= 0 |
| `opened_date` | DATE | Required | ISO 8601 Date (`YYYY-MM-DD`) | Date | Non-unique | Must be >= `Customer.created_at` date |

---

## 3. Loan (`Loan`)
Represents the specific installment loan contract with agreed principal, interest, and term.

| Field Name | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule & Foreign Key |
|---|---|---|---|---|---|---|
| `loan_id` | STRING | Required | Pattern: `LOAN-2026-[0-9]{6}` | ID string | Unique (PK) | Immutable primary key |
| `account_id` | STRING | Required | Pattern: `ACC-[0-9]{6}` | ID string | Non-unique | Foreign key -> `Account.account_id` |
| `customer_id` | STRING | Required | Pattern: `CUST-[0-9]{6}` | ID string | Non-unique | Foreign key -> `Customer.customer_id` |
| `loan_type` | STRING | Required | `PERSONAL`, `AUTO`, `MORTGAGE`, `SME_REVOLVING` | Enum | Non-unique | Standard loan product type |
| `principal_amount` | FLOAT | Required | Float between 500.00 and 50000.00 | USD ($) | Non-unique | Positive monetary value |
| `interest_rate` | FLOAT | Required | Float between 0.030 and 0.299 (3.0% to 29.9%) | Rate | Non-unique | APR percentage |
| `term_months` | INTEGER | Required | `12`, `24`, `36` | Months | Non-unique | Number of scheduled installments |
| `start_date` | DATE | Required | ISO 8601 Date (`YYYY-MM-DD`) | Date | Non-unique | Origination date |
| `maturity_date` | DATE | Required | ISO 8601 Date (`YYYY-MM-DD`) | Date | Non-unique | Equal to `start_date + term_months` |
| `monthly_installment_amount`| FLOAT | Required | Standard amortization formula PMT | USD ($) | Non-unique | PMT = `P * (r(1+r)^n)/((1+r)^n - 1)` |
| `current_balance` | FLOAT | Required | Float >= 0.00 | USD ($) | Non-unique | Sum of unpaid principal across installments |
| `total_arrears` | FLOAT | Required | Float >= 0.00 | USD ($) | Non-unique | Sum of overdue installment balances past due date |
| `days_past_due` | INTEGER | Required | Integer >= 0 | Days | Non-unique | Difference between reference date and oldest unpaid due date |
| `loan_status` | STRING | Required | `CURRENT`, `DELINQUENT`, `PAID_OFF`, `CHARGEOFF` | Enum | Non-unique | Derived from `total_arrears` and `days_past_due` |

---

## 4. Installment (`Installment`)
Represents an individual scheduled repayment slice with due date, principal, and interest breakdown.

| Field Name | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule & Foreign Key |
|---|---|---|---|---|---|---|
| `installment_id` | STRING | Required | Pattern: `INS-<loan_id>-[0-9]{3}` | ID string | Unique (PK) | Formatted as `INS-LOAN-2026-000001-001` |
| `loan_id` | STRING | Required | Pattern: `LOAN-2026-[0-9]{6}` | ID string | Non-unique | Foreign key -> `Loan.loan_id` |
| `installment_number` | INTEGER | Required | `1` to `Loan.term_months` | Sequence | Non-unique | Sequential integer without gaps |
| `due_date` | DATE | Required | ISO 8601 Date (`YYYY-MM-DD`) | Date | Non-unique | Exactly 1 month apart from previous installment |
| `principal_due` | FLOAT | Required | Float > 0.00 | USD ($) | Non-unique | Principal component of installment |
| `interest_due` | FLOAT | Required | Float >= 0.00 | USD ($) | Non-unique | Interest component of installment |
| `total_amount_due` | FLOAT | Required | `principal_due + interest_due` | USD ($) | Non-unique | Exact sum of principal and interest |
| `amount_paid` | FLOAT | Required | Float between 0.00 and `total_amount_due` | USD ($) | Non-unique | Cumulative payments credited |
| `remaining_balance` | FLOAT | Required | `total_amount_due - amount_paid` | USD ($) | Non-unique | Non-negative remaining arrears |
| `days_overdue` | INTEGER | Required | Integer >= 0 | Days | Non-unique | Max(0, `reference_date - due_date`) if unpaid |
| `status` | STRING | Required | `UPCOMING`, `CURRENT`, `OVERDUE`, `PAID`, `PARTIALLY_PAID` | Enum | Non-unique | Derived from remaining balance and due date |

---

## 5. DelinquencySnapshot (`DelinquencySnapshot`)
Represents a monthly point-in-time assessment of delinquency status, aging buckets, and roll rates.

| Field Name | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule & Foreign Key |
|---|---|---|---|---|---|---|
| `snapshot_id` | STRING | Required | Pattern: `SNP-2026-[0-9]{6}` | ID string | Unique (PK) | Primary key |
| `loan_id` | STRING | Required | Pattern: `LOAN-2026-[0-9]{6}` | ID string | Non-unique | Foreign key -> `Loan.loan_id` |
| `customer_id` | STRING | Required | Pattern: `CUST-[0-9]{6}` | ID string | Non-unique | Foreign key -> `Customer.customer_id` |
| `snapshot_date` | DATE | Required | ISO 8601 Date (`YYYY-MM-DD`) | Date | Non-unique | Date snapshot was taken |
| `days_past_due` | INTEGER | Required | Integer >= 0 | Days | Non-unique | Historical DPD at snapshot date |
| `delinquency_bucket` | STRING | Required | `CURRENT`, `30_DPD`, `60_DPD`, `90_DPD`, `120_PLUS_DPD` | Enum | Non-unique | Standard Basel/FDCPA delinquency stages |
| `total_arrears` | FLOAT | Required | Float >= 0.00 | USD ($) | Non-unique | Overdue balance at snapshot date |
| `total_principal_overdue`| FLOAT | Required | Float >= 0.00 | USD ($) | Non-unique | Unpaid overdue principal |
| `total_interest_overdue` | FLOAT | Required | Float >= 0.00 | USD ($) | Non-unique | Unpaid overdue interest |
| `missed_installments_count`| INTEGER| Required | Integer >= 0 | Count | Non-unique | Number of unpaid installments past due date |
| `risk_score` | FLOAT | Required | Float between 0.0 and 100.0 | Score | Non-unique | Behavioral delinquency score |

---

## 6. ContactPreference (`ContactPreference`)
Governs customer consent, channel preference, and lawful contact windows per TCPA & CFPB Reg F.

| Field Name | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule & Foreign Key |
|---|---|---|---|---|---|---|
| `preference_id` | STRING | Required | Pattern: `PREF-[0-9]{6}` | ID string | Unique (PK) | Primary key |
| `customer_id` | STRING | Required | Pattern: `CUST-[0-9]{6}` | ID string | Unique | Foreign key -> `Customer.customer_id` (1:1) |
| `preferred_channel` | STRING | Required | `PHONE`, `SMS`, `EMAIL`, `PORTAL` | Enum | Non-unique | Primary communication channel |
| `opt_in_phone` | BOOLEAN | Required | `0` or `1` | Boolean | Non-unique | Express consent for phone calls |
| `opt_in_sms` | BOOLEAN | Required | `0` or `1` | Boolean | Non-unique | Express consent for text messages |
| `opt_in_email` | BOOLEAN | Required | `0` or `1` | Boolean | Non-unique | Express consent for email notifications |
| `permissible_start_time` | STRING | Required | `HH:MM` (Default `08:00`) | Local Time | Non-unique | FDCPA standard earliest permissible hour |
| `permissible_end_time` | STRING | Required | `HH:MM` (Default `21:00`) | Local Time | Non-unique | FDCPA standard latest permissible hour |
| `do_not_call_employer` | BOOLEAN | Required | `0` or `1` (Default `1`) | Boolean | Non-unique | TCPA prohibition on workplace contact |
| `allowed_contact_days` | STRING | Required | Comma-delimited: `MON,TUE,WED,THU,FRI,SAT` | Enum CSV | Non-unique | Permissible days of the week |
| `last_consent_update` | TIMESTAMP | Required | ISO 8601 (`YYYY-MM-DDTHH:MM:SSZ`) | UTC | Non-unique | Audit timestamp for consent tracking |

---

## 7. CollectionCase (`CollectionCase`)
Represents the active collection workflow case managed by the operations team.

| Field Name | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule & Foreign Key |
|---|---|---|---|---|---|---|
| `case_id` | STRING | Required | Pattern: `COL-2026-[0-9]{6}` | ID string | Unique (PK) | Primary key |
| `loan_id` | STRING | Required | Pattern: `LOAN-2026-[0-9]{6}` | ID string | Unique | Foreign key -> `Loan.loan_id` (1:1 active) |
| `customer_id` | STRING | Required | Pattern: `CUST-[0-9]{6}` | ID string | Non-unique | Foreign key -> `Customer.customer_id` |
| `case_opened_date` | DATE | Required | ISO 8601 Date (`YYYY-MM-DD`) | Date | Non-unique | Date delinquency case initiated |
| `case_status` | STRING | Required | `ACTIVE`, `PENDING_PTP`, `UNDER_DISPUTE`, `HARDSHIP_HOLD`, `RESOLVED`, `CLOSED_PAID` | Enum | Non-unique | Valid lifecycle state |
| `priority_score` | FLOAT | Required | Float between 0.0 and 100.0 | Score | Non-unique | Deterministic scoring algorithm output |
| `priority_tier` | STRING | Required | `P1_CRITICAL`, `P2_HIGH`, `P3_MEDIUM`, `P4_LOW` | Enum | Non-unique | Partitioned by priority score |
| `assigned_agent_id` | STRING | Optional | Pattern: `AGENT-[0-9]{3}` or NULL | ID string | Non-unique | Assigned collector/analyst |
| `last_contact_date` | TIMESTAMP | Optional | ISO 8601 or NULL | UTC | Non-unique | Timestamp of most recent attempt |
| `next_scheduled_action`| TIMESTAMP | Optional | ISO 8601 or NULL | UTC | Non-unique | Calculated compliant scheduled time slot |
| `active_ptp_id` | STRING | Optional | Pattern: `PTP-2026-[0-9]{6}` or NULL | ID string | Non-unique | Reference to unexpired commitment |
| `total_attempts_count` | INTEGER | Required | Integer >= 0 | Count | Non-unique | Lifetime contact attempts on case |
| `weekly_attempts_count`| INTEGER | Required | Integer >= 0 | Count | Non-unique | Rolling 7-day attempt count (CFPB Reg F) |

---

## 8. ContactAttempt (`ContactAttempt`)
Immutable event record logging every outbound communication attempt and regulatory compliance evaluation.

| Field Name | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule & Foreign Key |
|---|---|---|---|---|---|---|
| `attempt_id` | STRING | Required | Pattern: `CTP-<case_id>-[0-9]{3}` | ID string | Unique (PK) | Formatted as `CTP-COL-2026-000001-001` |
| `case_id` | STRING | Required | Pattern: `COL-2026-[0-9]{6}` | ID string | Non-unique | Foreign key -> `CollectionCase.case_id` |
| `customer_id` | STRING | Required | Pattern: `CUST-[0-9]{6}` | ID string | Non-unique | Foreign key -> `Customer.customer_id` |
| `channel` | STRING | Required | `PHONE`, `SMS`, `EMAIL`, `LETTER` | Enum | Non-unique | Communication medium used |
| `attempt_timestamp` | TIMESTAMP | Required | ISO 8601 (`YYYY-MM-DDTHH:MM:SSZ`) | UTC | Non-unique | Exact outbound transmission time |
| `customer_local_time` | STRING | Required | Format `HH:MM` | Local Time | Non-unique | Calculated local time based on customer timezone |
| `is_permissible_window`| BOOLEAN | Required | `0` or `1` | Boolean | Non-unique | `1` if local time is between `08:00` and `21:00` |
| `rolling_7_day_count` | INTEGER | Required | Integer >= 0 | Count | Non-unique | Number of attempts in `[t - 7 days, t]` |
| `compliance_status` | STRING | Required | `COMPLIANT`, `QUIET_HOURS_VIOLATION`, `FREQUENCY_CAP_EXCEEDED`, `DISPUTE_HOLD_VIOLATION`, `HARDSHIP_HOLD_VIOLATION`, `CEASE_DESIST_VIOLATION` | Enum | Non-unique | Compliance rule evaluation output |
| `contact_outcome` | STRING | Required | `CONNECTED_PROMISE_MADE`, `CONNECTED_REFUSED_TO_PAY`, `CONNECTED_HARDSHIP_CLAIMED`, `CONNECTED_DISPUTED_DEBT`, `VOICEMAIL_LEFT`, `NO_ANSWER`, `EMAIL_SENT`, `SMS_DELIVERED`, `BLOCKED_BY_GUARDRAIL` | Enum | Non-unique | Interaction outcome |
| `agent_notes` | STRING | Optional | Text description (max 500 chars) | Text | Non-unique | Freeform collector notes |

---

## 9. PromiseToPay (`PromiseToPay`)
Represents an agreed payment commitment entered into by the customer.

| Field Name | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule & Foreign Key |
|---|---|---|---|---|---|---|
| `ptp_id` | STRING | Required | Pattern: `PTP-2026-[0-9]{6}` | ID string | Unique (PK) | Primary key |
| `case_id` | STRING | Required | Pattern: `COL-2026-[0-9]{6}` | ID string | Non-unique | Foreign key -> `CollectionCase.case_id` |
| `loan_id` | STRING | Required | Pattern: `LOAN-2026-[0-9]{6}` | ID string | Non-unique | Foreign key -> `Loan.loan_id` |
| `customer_id` | STRING | Required | Pattern: `CUST-[0-9]{6}` | ID string | Non-unique | Foreign key -> `Customer.customer_id` |
| `created_timestamp` | TIMESTAMP | Required | ISO 8601 (`YYYY-MM-DDTHH:MM:SSZ`) | UTC | Non-unique | Commitment creation timestamp |
| `promise_due_date` | DATE | Required | ISO 8601 Date (`YYYY-MM-DD`) | Date | Non-unique | Must be >= `created_timestamp` date |
| `promised_amount` | FLOAT | Required | Float > 0.00 | USD ($) | Non-unique | Must be <= `current_arrears_at_promise` (except deliberate anomaly) |
| `current_arrears_at_promise`| FLOAT | Required | Float >= 0.00 | USD ($) | Non-unique | Snapshot of total arrears when promise taken |
| `ptp_status` | STRING | Required | `PENDING`, `KEPT`, `PARTIALLY_KEPT`, `BROKEN`, `CANCELLED` | Enum | Non-unique | Commitment lifecycle status |
| `fulfilled_amount` | FLOAT | Required | Float >= 0.00 | USD ($) | Non-unique | Reconciled payment amount received |
| `fulfillment_date` | DATE | Optional | ISO 8601 Date or NULL | Date | Non-unique | Date when payment was received |
| `reconciled_payment_id`| STRING | Optional | Pattern: `PMT-2026-[0-9]{6}` or NULL | ID string | Non-unique | Foreign key -> `Payment.payment_id` |

---

## 10. Payment (`Payment`)
Represents monetary repayments received from borrowers and allocated to amortized installments.

| Field Name | Type | Req/Opt | Allowed Values / Format | Units | Uniqueness | Validation Rule & Foreign Key |
|---|---|---|---|---|---|---|
| `payment_id` | STRING | Required | Pattern: `PMT-2026-[0-9]{6}` | ID string | Unique (PK) | Primary key |
| `loan_id` | STRING | Required | Pattern: `LOAN-2026-[0-9]{6}` | ID string | Non-unique | Foreign key -> `Loan.loan_id` |
| `account_id` | STRING | Required | Pattern: `ACC-[0-9]{6}` | ID string | Non-unique | Foreign key -> `Account.account_id` |
| `customer_id` | STRING | Required | Pattern: `CUST-[0-9]{6}` | ID string | Non-unique | Foreign key -> `Customer.customer_id` |
| `payment_date` | DATE | Required | ISO 8601 Date (`YYYY-MM-DD`) | Date | Non-unique | Posting date |
| `amount` | FLOAT | Required | Float > 0.00 | USD ($) | Non-unique | Amount paid in USD |
| `payment_method` | STRING | Required | `ACH`, `DEBIT_CARD`, `WIRE`, `CHECK` | Enum | Non-unique | Transaction rail |
| `allocated_installment_id`| STRING | Required | Pattern: `INS-<loan_id>-[0-9]{3}` | ID string | Non-unique | Foreign key -> `Installment.installment_id` |
| `allocation_status` | STRING | Required | `ALLOCATED_CORRECTLY`, `MISALLOCATED_WRONG_INSTALLMENT` | Enum | Non-unique | Waterfall adherence check |
| `reconciled_ptp_id` | STRING | Optional | Pattern: `PTP-2026-[0-9]{6}` or NULL | ID string | Non-unique | Foreign key -> `PromiseToPay.ptp_id` |
| `payment_reference` | STRING | Required | Pattern: `REF-[A-Z0-9]{10}` | String | Unique | External clearing reference number |

---

## 11. Ground Truth & Edge Case Manifest (`GroundTruthAnomaly`)
Stored separately in `ground_truth.csv` and `ground_truth.json` for validation and auditing. Never leaked into production feature tables.

| Field Name | Type | Req/Opt | Allowed Values / Format | Description & Detection Rule |
|---|---|---|---|---|
| `anomaly_id` | STRING | Required | Pattern: `ANO-[0-9]{6}` | Unique identifier for the anomaly record |
| `entity_type` | STRING | Required | `Loan`, `CollectionCase`, `ContactAttempt`, `PromiseToPay`, `Payment` | Target table where edge case was injected |
| `entity_id` | STRING | Required | ID matching the affected entity | Foreign identifier of the injected anomaly row |
| `issue_type` | STRING | Required | `PAID_ACCOUNT_REMAINS_IN_COLLECTION`<br>`CONTACT_OUTSIDE_ALLOWED_WINDOW`<br>`PAYMENT_ALLOCATED_TO_WRONG_INSTALLMENT`<br>`PROMISE_AMOUNT_EXCEEDS_ARREARS`<br>`DISPUTED_DEBT_TREATED_AS_CONFIRMED` | Standardized edge case category |
| `description` | STRING | Required | Human-readable explanation | Detailed narrative of the simulated flaw |
| `expected_decision` | STRING | Required | `CLOSE_CASE_AND_REFUND`, `FLAG_VIOLATION_AND_REPRIMAND`, `REALLOCATE_WATERFALL_WATERLINE`, `REVISE_PROMISE_AMOUNT`, `FREEZE_CONTACT_AND_VALIDATE` | Regulatory/operational remediation action |
| `detection_rule` | STRING | Required | Algorithmic condition | Exact SQL/Python rule that identifies the anomaly |
| `severity` | STRING | Required | `CRITICAL`, `HIGH`, `MEDIUM` | Regulatory penalty risk level |
