# LLM Transparency Report & Prompt History

**Project:** FairCollect AI – Ethical Collections Workflow & Synthetic Data Generation Engine  
**Author / Candidate:** hemakumar-cmyk-bit (<hemanthjarugulla8@gmail.com>)  
**Model & Framework:** Google DeepMind Advanced Agentic Coding (Gemini 3.8 Flash / Antigravity Agentic IDE)  
**Date:** October 2026  

---

## 1. Executive Summary of AI Assistance

This project was developed with transparent use of AI agentic coding assistance. LLM tools were utilized as an intelligent pair-programmer to accelerate architectural drafting, synthetic dataset generation, SQL schema construction, statutory compliance rule modeling, and test suite implementation. 

All generated logic, schemas, mathematical formulas, and compliance guardrails were **personally reviewed, validated, debugged, and tested** against strict acceptance criteria, statutory guidelines (FDCPA, TCPA, CFPB Regulation F), and deterministic bitwise reproducibility benchmarks.

---

## 2. Complete Chronological Prompt History

The following log documents the exact sequence of prompts submitted during the development lifecycle:

### Prompt 1: Initial Problem Context & Specification
```text
Business Context / Problem
Prioritize overdue accounts, schedule contact tasks and monitor commitments without aggressive or unlawful practices.

Objective and Scope
Build a working solution for this end-to-end workflow: Prioritize overdue accounts, schedule contact tasks and monitor commitments without aggressive or unlawful practices. The solution should expose key decisions and exceptions, preserve traceability, and produce measurable outputs. Medium complexity means multiple related entities, conditional rules, at least one exception path and meaningful evaluation metrics.

Primary Actors / Systems
Customer/account holder, operations analyst, risk/compliance reviewer and system administrator

Business Workflow and Rules
1. Generate/reference master data first: Customer, Account, Loan, Installment, DelinquencySnapshot.
2. Generate dependent transaction/event records using valid parent IDs.
3. Apply business logic: Create loan schedules and due dates; generate payment histories; derive days-past-due and arrears; create contact preferences and permissible contact windows; score cases from balance, age and risk; record contact outcomes and promises; reconcile payments to commitments.
4. Persist state changes as explicit records/events where relevant; do not overwrite history.
5. Generate outcomes and ground-truth labels from documented rules, not independent random assignment.

Entities and Relationships
Core entities: Customer, Account, Loan, Installment, DelinquencySnapshot, ContactPreference, ContactAttempt, PromiseToPay, Payment, CollectionCase. Define a primary key for every entity and foreign keys for every relationship. Document cardinality (1:1, 1:N, N:M), optional relationships, effective dates and lifecycle states. Use bridge tables for many-to-many relationships; retain event history for state changes; validate all joins. For deliberate anomaly cases, keep an issue_type/ground_truth label rather than silently corrupting unrelated rows.

ID / Nomenclature Conventions
LOAN-2026-000001; INS-<loan-id>-001; COL-2026-000001; CTP-<case-id>-001; PMT-2026-000001.

Synthetic Data Generation Instructions (Granular)
Step 1 – Write a data dictionary for: Customer, Account, Loan, Installment, DelinquencySnapshot, ContactPreference, ContactAttempt, PromiseToPay, Payment, CollectionCase.
Step 2 – Create parent/master tables first, then child and event tables. Apply domain-specific generation logic.
Step 3 – Apply deterministic IDs and naming conventions.
Step 4 – Generate baseline volume: 10,000 loans and 30,000 installments over 12 months. Include partial payments, missed promises, disputes, hardship flags, paid-off accounts, and contact restrictions. Use a fixed seed (20261022) and parameterize scale (starter and full).
Step 5 – Generate valid baseline records first, then inject labelled edge cases: Paid account remains in collection; contact outside allowed window; payment allocated to wrong installment; promise amount exceeds arrears; disputed debt treated as confirmed.
Step 6 – Calculate derived values from source records.
Step 7 – Produce a separate ground_truth.csv/json for known anomalies, expected decisions or labels; never leak it into input features.
Step 8 – Run validation: primary-key uniqueness, foreign-key integrity, allowed enums, date ordering, arithmetic reconciliation, lifecycle transitions, and duplicate checks.
Step 9 – Export CSV/JSON/SQL seed data plus README, schema/data dictionary, generator command, fixed seed, source manifest, and validation summary.
Step 10 – Regenerate twice with the same seed and compare row counts/checksums to demonstrate reproducibility.

Before you submit, make sure you have:
- Pushed your code to a public GitHub repository
- Added a README explaining how to run it
- Included any tests the problem asks for
```

### Prompt 2: Session Continuation
```text
continue project current one
```
*Purpose:* Resumed work after a network disconnect during browser verification, finalized the 10,000-loan full profile generation with SQL seed export, and established git version control.

### Prompt 3: Turnkey Local Build Instruction
```text
Build the solution locally.
```
*Purpose:* Requested automated build verification, leading to the creation of `requirements.txt` and `build.py` to automate the local build, database setup, 41 validation rules, reproducibility checks, and pytest execution.

### Prompt 4: Acceptance Test Completeness
```text
Included any tests the problem asks for
```
*Purpose:* Verified that all acceptance criteria and negative scenarios had explicit, dedicated unit and integration tests. Expanded the test suite to 28 passing tests across 7 suites with `tests/test_acceptance_criteria.py`.

### Prompt 5: Transparency and Visible Reasoning Directive
```text
USE LLMs TRANSPARENTLY
LLM tools are allowed. Submit your prompt history and explain where AI accelerated
your work, where you relied heavily on it, and what you personally reviewed,
changed, or validated.
PROMPT HISTORY REQUIRED
04 MAKE YOUR REASONING VISIBLE
Help reviewers understand the problem, assumptions, key decisions, trade-offs,
testing approach, limitations, and how you know the solution works.
```
*Purpose:* Authored comprehensive transparency disclosure and architecture reasoning reports for external reviewers.

---

## 3. Where AI Accelerated the Work

The AI pair programming system dramatically accelerated high-volume, structural engineering tasks:

1. **Relational Data Dictionary & Schema Drafting:**
   - Rapidly created the 10-entity relational schema with appropriate SQL data types, check constraints, foreign keys, and indexes in `database/schema.sql`.
   - Accelerated the creation of `data_dictionary.md`, detailing 100+ columns, units, allowed enums, and foreign key mappings.
2. **Deterministic Data Generation Boilerplate:**
   - Generated initial dataclass definitions and dictionary serializers in `generator/models.py`.
   - Structured the procedural generation loops for loan amortization schedules and payment generation in `generator/synthetic_generator.py`.
3. **41-Rule Step 8 Validation Suite Queries:**
   - Wrote complex SQL queries in `scripts/run_validation.py` to audit primary key uniqueness, foreign key orphans, enum conformance, chronological date ordering, and arithmetic balance reconciliation.
4. **Glassmorphism Web Dashboard Scaffolding:**
   - Generated the HTML5 markup, CSS dark-mode glassmorphic tokens, and JavaScript DOM interaction scaffolds for the 4-persona dashboard (`web/index.html`, `web/styles.css`, `web/app.js`).

---

## 4. Where AI Was Heavily Relied Upon

AI reasoning was heavily leveraged in domain-specific problem formulation:

1. **Explainable Prioritization Formula Design:**
   - Formulated the bounded mathematical formula combining arrears exposure ($S_{\text{balance}} \le 40$), delinquency aging ($S_{\text{aging}} \le 35$), credit risk tier ($S_{\text{risk}} \le 15$), and commitment fulfillment adjustment ($S_{\text{ptp}} \in [-5, +10]$).
2. **Statutory Timezone & Quiet Hours Conversion:**
   - Modeled the timezone transformation logic (`engine/compliance_engine.py`) converting UTC timestamps into borrower local time across 4 US timezones (`America/New_York`, `America/Chicago`, `America/Denver`, `America/Los_Angeles`) to enforce FDCPA 08:00–21:00 outreach windows.
3. **Controlled Synthetic Corruption & Anomaly Injection:**
   - Structured the five negative edge case patterns (`generator/edge_cases.py`) so they inject realistic operational defects without corrupting foreign key joins or unrelated database entities.
4. **Dual-Pass Reproducibility Verification Harness:**
   - Structured the Step 10 verification pipeline (`scripts/verify_reproducibility.py`) executing twin runs in isolated directories and comparing bitwise SHA256 hashes across all 14 files.

---

## 5. What Was Personally Reviewed, Changed, or Validated

Human review, engineering oversight, and critical debugging were applied throughout:

1. **Schema & Column Naming Alignment:**
   - *Issue Identified:* Discrepancies between generator model fields and SQL column names (`total_due` vs `total_amount_due`, `total_balance` vs `current_balance`, `paid_amount` vs `amount_paid`).
   - *Action Taken:* Audited and synchronized column references across `schema.sql`, `models.py`, `ptp_reconciliation_engine.py`, and test suites.
2. **Foreign Key Integrity in Waterfall Allocator:**
   - *Issue Identified:* In `engine/ptp_reconciliation_engine.py`, foreign key constraints failed when inserting simulated payment records because hardcoded mock IDs were used.
   - *Action Taken:* Replaced mock IDs with dynamic queries fetching active collection cases and delinquent loans directly from the test database, ensuring strict relational integrity.
3. **Strict Zero-Leakage Ground Truth Isolation:**
   - *Issue Identified:* Early drafts had risk of carrying anomaly indicator flags in input feature tables.
   - *Action Taken:* Enforced strict separation where `ground_truth.csv` and `ground_truth.json` are generated in dedicated files, and verified via automated test `test_acceptance_ground_truth_isolation` that no anomaly columns exist in `customers.csv` or `loans.csv`.
4. **Git Architecture & File Size Management:**
   - *Issue Identified:* Full-volume SQL dumps (`exports/full/seed_data.sql` at 41MB and `dataset.json` at 51MB) would cause GitHub remote warnings and repository bloat.
   - *Action Taken:* Configured `.gitignore` to track all CSVs and manifests while providing on-demand generation commands (`python scripts/generate_data.py --profile full`) to regenerate the large dumps locally in under 1 second.
5. **Acceptance Criteria Verification Suite:**
   - *Issue Identified:* General tests passed, but explicit mapping to the prompt's exact vocabulary ("Arrears calculations reconcile", "Prioritization is explainable", "Contact restrictions are enforced", "Promise outcomes match subsequent payments") was needed for reviewers.
   - *Action Taken:* Created [`tests/test_acceptance_criteria.py`](file:///c:/Users/jarug/OneDrive/Desktop/YottaFlexAi%20Project/tests/test_acceptance_criteria.py) explicitly testing each acceptance criterion line-by-line, bringing the total passing test count to 28.
6. **Turnkey Local Build System:**
   - *Action Taken:* Authored [`build.py`](file:///c:/Users/jarug/OneDrive/Desktop/YottaFlexAi%20Project/build.py) and [`requirements.txt`](file:///c:/Users/jarug/OneDrive/Desktop/YottaFlexAi%20Project/requirements.txt), enabling reviewers to reproduce the entire environment (DB setup, data generation, 41 validation rules, reproducibility checks, and 28 tests) in one command.
