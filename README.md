# FairCollect AI: Ethical Collections Workflow & Synthetic Data Generation Engine

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-green.svg)](https://fastapi.tiangolo.com)
[![Pytest](https://img.shields.io/badge/pytest-28%20passed-brightgreen.svg)](tests/)
[![Validation](https://img.shields.io/badge/Validation%20Suite-41%20Passed-success.svg)](scripts/run_validation.py)
[![Compliance](https://img.shields.io/badge/Compliance-FDCPA%20%7C%20TCPA-blueviolet.svg)](engine/compliance_engine.py)
[![Reproducibility](https://img.shields.io/badge/Reproducibility-100%25%20Bitwise%20SHA256-blue.svg)](scripts/verify_reproducibility.py)

> **Reviewer Resources & Transparency Disclosures:**  
> • 📋 **[LLM Transparency Report & Complete Prompt History](LLM_TRANSPARENCY_REPORT.md)** (Prompt history, AI acceleration, human review & validation)  
> • 🧠 **[Architectural Reasoning & Decision Report](REASONING_AND_ARCHITECTURE_DECISIONS.md)** (Problem understanding, assumptions, trade-offs, and proof of correctness)  
> • 📖 **[Comprehensive Data Dictionary](data_dictionary.md)** (10 core entities, schema, constraints, and cardinalities)

---

## 1. Problem Context & Solution Overview

In contemporary retail credit and loan servicing, traditional debt recovery workflows often rely on aggressive outreach, arbitrary scheduling, and opaque prioritization heuristics. These practices lead to **FDCPA / TCPA statutory violations**, customer harassment, regulatory fines, and reputational damage.

**FairCollect AI** provides a transparent, lawful, and mathematically sound end-to-end collections intelligence platform and deterministic synthetic data generator. It solves the core industry challenge:

> **"Prioritize overdue accounts, schedule contact tasks, and monitor commitments without aggressive or unlawful practices."**

The platform exposes every decision, maintains an immutable relational audit trail, enforces statutory guardrails, and provides tailored, interactive interfaces for **four primary personas**:
1. **Operations Analyst**: Prioritized account queue with explainable scoring factor meters, permissible contact schedules, and PTP recording.
2. **Risk & Compliance Reviewer**: Real-time auditing of contact attempts, quiet-hours compliance, dispute/hardship moratoriums, and automated remediation for regulatory anomalies.
3. **Customer / Account Holder**: Transparent self-service portal showing amortized installments, waterfall payment simulation, and hardship/dispute requests.
4. **System Administrator**: Portfolio performance analytics and one-click execution of the 41-rule data integrity suite.

---

## 2. Architecture & Core Workflow

```
┌────────────────────────────────────────────────────────────────────────┐
│              10-Step Deterministic Synthetic Data Generator            │
│                 (Fixed Seed: 20261022 | Starter & Full Profiles)       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
    ┌───────────────────────────────┴──────────────────────────────┐
    ▼                                                              ▼
┌───────────────────────────────┐              ┌─────────────────────────────────┐
│     Relational Database       │              │     Multi-Format Seed Exports   │
│  (SQLite: 10 Core Tables +    │              │  (CSVs, JSON, SQL seed,         │
│   Ground Truth Anomaly Table) │              │   Manifest with SHA256 Hashes)  │
└───────────────┬───────────────┘              └─────────────────────────────────┘
                │
    ┌───────────┴──────────────────────────────────────────────────┐
    ▼                                                              ▼
┌─────────────────────────────────┐              ┌─────────────────────────────────┐
│     Business Engine Services    │              │    FastAPI Application Layer   │
│ • Prioritization Engine         │              │ • REST Endpoints (/api/cases,   │
│ • Compliance Guardrails (FDCPA) │◄────────────►│   /api/compliance, /api/admin)  │
│ • Permissible Window Scheduler  │              │ • Real-time Validation Bridge   │
│ • Reconciliation & Arrears Calc │              │ • Automated Remediation Webhook │
│ • Regulatory Anomaly Detector   │              └────────────────┬────────────────┘
└─────────────────────────────────┘                               │
                                                                  ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                   Glassmorphism Multi-Persona Web Application                    │
│   [Operations Analyst]   [Risk & Compliance]   [Customer Portal]   [Admin Suite] │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Key Capabilities & Technical Features

### A. Explainable Prioritization Algorithm
Accounts are scored transparently on a scale of `0.0` to `100.0` points, mapping to urgency tiers (**P1 Critical**, **P2 High**, **P3 Medium**, **P4 Normal**). Every score factor is mathematically explainable and visible in the UI:
$$\text{Priority Score} = \min(100.0, \; S_{\text{balance}} + S_{\text{aging}} + S_{\text{risk}} + S_{\text{ptp}})$$
- **Arrears Exposure Factor ($S_{\text{balance}}$)**: $\min(40.0, \; \frac{\text{Arrears}}{5000.0} \times 40.0)$
- **Aging & Delinquency Factor ($S_{\text{aging}}$)**: 
  - $\text{DPD} \ge 90$: $35.0$ pts
  - $\text{DPD} \in [60, 89]$: $25.0$ pts
  - $\text{DPD} \in [30, 59]$: $15.0$ pts
  - $\text{DPD} < 30$: $5.0$ pts
- **Credit Risk Segment ($S_{\text{risk}}$)**: `CRITICAL` ($15.0$ pts), `HIGH` ($10.0$ pts), `MEDIUM` ($5.0$ pts), `LOW` ($0.0$ pts)
- **Broken Commitment History ($S_{\text{ptp}}$)**: $+10.0$ pts for broken promises, $-5.0$ pts for kept promises.

### B. Statutory Ethical & Compliance Guardrails
Outbound communications are governed by real-time rules:
1. **FDCPA Quiet Hours Enforcement**: Outreach is legally restricted to **08:00 to 21:00** in the **consumer's local timezone** (`America/New_York`, `America/Chicago`, `America/Denver`, `America/Los_Angeles`).
2. **FDCPA Section 805(c) Cease & Desist**: If a consumer issues a cease-and-desist notice, all outbound communication attempts are instantly and permanently blocked.
3. **Hardship Moratorium**: Active temporary unemployment, medical emergency, or natural disaster freezes collections immediately.
4. **FDCPA Section 809 Dispute Moratorium**: Debts under active dispute cannot be pursued until formal debt validation is completed.
5. **TCPA & CFPB 7-in-7 Frequency Cap**: A maximum of 7 telephone contact attempts are allowed within any rolling 7-day window.

### C. Injected Edge Cases & Separate Ground Truth
To evaluate risk detection and ML fairness without data leakage, 5 negative scenarios are deterministically injected and recorded in a separate `ground_truth.csv` and `ground_truth.json`:
1. `PAID_ACCOUNT_IN_COLLECTION`: Account paid in full but case erroneously left active.
2. `OUTSIDE_PERMISSIBLE_WINDOW`: Outbound contact attempt logged outside 08:00–21:00 consumer local time.
3. `MISALLOCATED_PAYMENT`: Payment allocated to an incorrect or non-chronological installment.
4. `PTP_EXCEEDS_ARREARS`: Promise to pay commitment exceeding total arrears balance.
5. `DISPUTED_DEBT_CONFIRMED`: Disputed account contacted as if confirmed without resolution.

The separate ground-truth files preserve complete isolation—no anomaly labels leak into model features.

---

## 4. Entity-Relationship Model (10 Core Entities)

All IDs adhere to deterministic naming conventions:
- Loans: `LOAN-2026-000001`
- Installments: `INS-<loan-id>-001`
- Collection Cases: `COL-2026-000001`
- Contact Attempts: `CTP-<case-id>-001`
- Payments: `PMT-2026-000001`

```
[Customer] (1) ────< (N) [Account] (1) ────< (N) [Loan] (1) ────< (N) [Installment]
   │                       │                    │
   │ (1:1)                 │ (1:N)              │ (1:1)
   ▼                       ▼                    ▼
[ContactPreference]    [Payment]           [CollectionCase] (1) ────< (N) [ContactAttempt]
                                                │
                                                │ (1:N)
                                                ▼
                                         [PromiseToPay]
```

Full column specifications, allowed enums, data types, and foreign key constraints are documented in [data_dictionary.md](data_dictionary.md).

---

## 5. Quick Start & Execution Guide

### Prerequisites
- Python 3.10+ (tested on Python 3.12)
- Virtual environment (recommended)

Install dependencies:
```bash
pip install -r requirements.txt
```

### Turnkey One-Click Local Build
To automatically initialize the database, generate data, run all 41 validation rules, verify reproducibility, and run the 19 pytest tests in a single command:
```bash
python build.py
```

---

### Step-by-Step Manual Commands

### 1. Generate Synthetic Data
Run the CLI generator with a fixed seed (`20261022`):

- **Starter Profile** (500 loans, interactive demo):
  ```bash
  python scripts/generate_data.py --profile starter
  ```
- **Full Volume Profile** (10,000 loans, 34,560 installments over 12 months):
  ```bash
  python scripts/generate_data.py --profile full --skip-db
  ```

Output exports are written to `exports/<profile>/` (including CSVs, `dataset.json`, `ground_truth.json`, `seed_data.sql`, and `manifest.json` with SHA256 hashes).

### 2. Run the 41-Rule Validation & Acceptance Suite
Verify referential integrity, primary-key uniqueness, domain enums, date ordering, arithmetic reconciliation, and lifecycle transitions:
```bash
python scripts/run_validation.py
```
*Expected Output: `41 / 41 Passed [PASS]`.*

### 3. Verify Deterministic Reproducibility
Execute Step 10 reproducibility verification to regenerate two independent passes with the same seed and compare row counts and SHA256 checksums:
```bash
python scripts/verify_reproducibility.py
```
*Expected Output: `REPRODUCIBILITY VERIFICATION: 100% SUCCESS` (Bitwise SHA256 match).*

### 4. Run Pytest Suite
Run the 28 automated unit, acceptance, and regression tests across 7 test suites:
```bash
pytest
```
*Expected Output: `28 passed in ~1.5s`.*

### 5. Launch Web Application & API
Start the FastAPI server:
```bash
python scripts/run_server.py
```
Then open your browser at:
```
http://127.0.0.1:8000/
```

---

## 6. Web Application Personas & Tour

| Persona | Tab Title | Key Interactions |
|---|---|---|
| **Operations Analyst** | Worklist & Case Review | • Filter cases by Priority Tier (P1–P4) or search by ID.<br>• Open **Review & Act** modal with real-time explainable score meter.<br>• Check permissible local time contact windows.<br>• Record customer promises to pay (PTP). |
| **Risk & Compliance** | Compliance & Audit | • Live monitoring of quiet hours violations and blocked guardrails.<br>• Inspect the **Anomaly Detection Center**.<br>• One-click **Remediate Now** action to cure regulatory edge cases with instant toast feedback. |
| **Customer Portal** | Self-Service Portal | • Simulated borrower view (e.g. Joshua White `CUST-000018`).<br>• View past due balance, dispute status, and active protections.<br>• Interactive **Waterfall Payment Simulation** allocating payments across oldest installments first. |
| **System Administrator** | Portfolio & Health Suite | • Portfolio-level capital metrics (Originated Principal, Outstanding Balance, Arrears).<br>• Interactive **Step 8 Validation & Integrity Suite** button running all 41 integrity tests live from the UI. |

---

## 7. Project Structure

```
├── README.md                      # Comprehensive project documentation
├── LLM_TRANSPARENCY_REPORT.md     # Full prompt history, AI acceleration & human review disclosure
├── REASONING_AND_ARCHITECTURE_DECISIONS.md # Assumptions, key decisions, trade-offs & proof points
├── data_dictionary.md             # Granular schema, data types, constraints & validation rules
├── requirements.txt               # Pinned Python package dependencies
├── build.py                       # Turnkey local build and test execution script
├── pytest.ini                     # Pytest configuration
├── .gitignore                     # Git ignore rules
│
├── api/
│   └── server.py                  # FastAPI application & REST endpoints
│
├── database/
│   ├── db.py                      # SQLite connection management & table initializers
│   └── schema.sql                 # DDL definitions, primary/foreign keys, and indexes
│
├── engine/
│   ├── anomaly_detector.py        # Detects injected anomalies and provides remediation paths
│   ├── compliance_engine.py       # FDCPA/TCPA quiet-hours, hardship, and dispute guardrails
│   ├── prioritization_engine.py   # Explainable prioritization scoring algorithm
│   ├── ptp_reconciliation_engine.py # Waterfall payment-to-installment reconciliation
│   └── scheduler_engine.py        # Permissible contact window slot generator
│
├── generator/
│   ├── config.py                  # Scale profiles, default seed (20261022), weights & enums
│   ├── edge_cases.py              # Injects 5 labelled negative edge cases
│   ├── models.py                  # Dataclasses and serializers for all 10 entities
│   └── synthetic_generator.py     # Deterministic generation engine with CSV/JSON/SQL exporters
│
├── scripts/
│   ├── generate_data.py           # CLI for starter/full synthetic generation
│   ├── run_server.py              # Uvicorn launcher for the web application
│   ├── run_validation.py          # 41-rule acceptance & integrity test suite
│   └── verify_reproducibility.py  # Step 10 dual-run checksum verification script
│
├── tests/
│   ├── test_acceptance_criteria.py# Maps 1-to-1 to all problem acceptance criteria & edge cases
│   ├── test_compliance_rules.py   # FDCPA quiet hours, hardship, dispute & 7-in-7 frequency cap
│   ├── test_edge_cases.py         # Detection and auditable remediation for all 5 negative scenarios
│   ├── test_integrity.py          # Full 41-rule schema validation assertion
│   ├── test_prioritization.py     # Prioritization score math, factor explainability & tiering
│   ├── test_reconciliation.py     # Waterfall accounting and PTP fulfillment/breakage
│   └── test_reproducibility.py    # Fixed-seed bitwise SHA256 reproducibility test
│
├── web/
│   ├── index.html                 # Semantic HTML5 multi-persona dashboard
│   ├── styles.css                 # Glassmorphic dark-mode CSS design system
│   └── app.js                     # Dynamic state management, API calls, and modals
│
└── exports/
    ├── starter/                   # 500 loans (CSVs, JSON, SQL seed, manifest)
    └── full/                      # 10,000 loans, 34,560 installments (CSVs, manifest, etc.)
```

---

## 8. Pushing to a Public GitHub Repository

To publish this project to your GitHub account:

1. **Create an empty public repository** on GitHub (e.g. `faircollect-ai` or `ethical-collections-engine`).
2. Run the following commands in the project root:
   ```bash
   git add .
   git commit -m "feat: complete fair collections engine, synthetic data generator, and web application"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo-name>.git
   git push -u origin main
   ```

---

## 9. Regulatory & Ethical Provenance

- **100% Synthetic Data**: All identities, phone numbers, email addresses, balances, and account records are procedurally generated using deterministic random seeds. No PII or proprietary banking data was collected or utilized.
- **Statutory Alignment**: Architecture adheres to the Fair Debt Collection Practices Act (FDCPA, 15 U.S.C. § 1692 et seq.), the Telephone Consumer Protection Act (TCPA), and Consumer Financial Protection Bureau (CFPB) Regulation F (12 CFR Part 1006).
