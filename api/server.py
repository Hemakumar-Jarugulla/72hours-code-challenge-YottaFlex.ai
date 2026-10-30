"""
FastAPI REST Application & Web Server.
Exposes end-to-end endpoints for:
- Operations Analyst (Prioritization worklist, compliant outreach, PTP recording)
- Compliance Reviewer (Anomaly scans, 1-click remediation, audit trail, guardrails)
- Customer / Account Holder (Self-service loan portal, repayment waterfall, commitments)
- System Administrator (Generator trigger, validation runner, metrics, export download)
"""

import os
import sys
import sqlite3
import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# Add workspace to path
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WORKSPACE_DIR)

from database.db import get_db_connection, init_database, log_audit_event
from engine.compliance_engine import evaluate_contact_compliance, check_quiet_hours
from engine.prioritization_engine import calculate_case_priority
from engine.scheduler_engine import compute_next_contact_slot
from engine.ptp_reconciliation_engine import allocate_payment_waterfall, evaluate_overdue_ptps
from engine.anomaly_detector import scan_anomalies, remediate_anomaly
from scripts.run_validation import ValidationSuite
from generator.synthetic_generator import SyntheticDataGenerator

app = FastAPI(
    title="Fair Collections & Recovery Engine API",
    description="Compliant debt prioritization, contact scheduling, and commitment reconciliation system.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------------------
# Request Schemas
# -------------------------------------------------------------
class ContactAttemptRequest(BaseModel):
    channel: str = "PHONE"
    attempt_timestamp_utc: Optional[str] = None
    agent_notes: Optional[str] = None
    force_override: bool = False  # If True, deliberately forces through (for testing compliance reviewer)

class PromiseRequest(BaseModel):
    promise_due_date: str
    promised_amount: float

class PaymentRequest(BaseModel):
    amount: float
    payment_method: str = "ACH"
    ptp_id: Optional[str] = None
    actor_persona: str = "CUSTOMER"
    actor_id: str = "SELF_SERVICE"

class CustomerPreferenceUpdate(BaseModel):
    preferred_channel: str
    opt_in_phone: int
    opt_in_sms: int
    opt_in_email: int
    permissible_start_time: str
    permissible_end_time: str

class HardshipDisputeRequest(BaseModel):
    action_type: str  # 'HARDSHIP' or 'DISPUTE'
    status_value: str
    notes: Optional[str] = None

class RemediateRequest(BaseModel):
    anomaly_id: str
    issue_type: str
    entity_id: str
    actor_id: str = "COMPLIANCE_OFFICER"

class GenerateRequest(BaseModel):
    profile: str = "starter"
    seed: int = 20261022


# -------------------------------------------------------------
# 1. Analyst Persona Endpoints
# -------------------------------------------------------------
@app.get("/api/cases")
def get_cases(
    tier: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """Retrieves prioritized collection cases with borrower contact details and status."""
    conn = get_db_connection()
    q = """
    SELECT c.case_id, c.loan_id, c.customer_id, c.case_opened_date, c.case_status,
           c.priority_score, c.priority_tier, c.assigned_agent_id, c.last_contact_date,
           c.next_scheduled_action, c.active_ptp_id, c.total_attempts_count, c.weekly_attempts_count,
           cust.first_name, cust.last_name, cust.phone_number, cust.email, cust.timezone,
           cust.risk_segment, cust.hardship_status, cust.dispute_status, cust.cease_desist_flag,
           l.principal_amount, l.current_balance, l.total_arrears, l.days_past_due, l.loan_status,
           pref.preferred_channel, pref.opt_in_phone, pref.opt_in_sms, pref.opt_in_email,
           pref.permissible_start_time, pref.permissible_end_time
    FROM collection_cases c
    JOIN customers cust ON c.customer_id = cust.customer_id
    JOIN loans l ON c.loan_id = l.loan_id
    LEFT JOIN contact_preferences pref ON c.customer_id = pref.customer_id
    WHERE 1=1
    """
    params = []
    if tier:
        q += " AND c.priority_tier = ?"
        params.append(tier)
    if status:
        q += " AND c.case_status = ?"
        params.append(status)
    if search:
        q += " AND (cust.first_name LIKE ? OR cust.last_name LIKE ? OR c.case_id LIKE ? OR l.loan_id LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, term])

    q += " ORDER BY c.priority_score DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(q, params).fetchall()
    
    total_count = conn.execute("SELECT COUNT(*) as c FROM collection_cases").fetchone()["c"]
    conn.close()
    return {"total": total_count, "items": [dict(r) for r in rows]}


@app.get("/api/cases/{case_id}/details")
def get_case_details(case_id: str):
    """Fetches detailed case information including installments, attempts, and PTPs."""
    conn = get_db_connection()
    case = conn.execute("SELECT * FROM collection_cases WHERE case_id = ?", (case_id,)).fetchone()
    if not case:
        conn.close()
        raise HTTPException(status_code=404, detail="Case not found")

    cust = conn.execute("SELECT * FROM customers WHERE customer_id = ?", (case["customer_id"],)).fetchone()
    loan = conn.execute("SELECT * FROM loans WHERE loan_id = ?", (case["loan_id"],)).fetchone()
    pref = conn.execute("SELECT * FROM contact_preferences WHERE customer_id = ?", (case["customer_id"],)).fetchone()
    
    installments = conn.execute(
        "SELECT * FROM installments WHERE loan_id = ? ORDER BY installment_number ASC",
        (case["loan_id"],)
    ).fetchall()

    attempts = conn.execute(
        "SELECT * FROM contact_attempts WHERE case_id = ? ORDER BY attempt_timestamp DESC",
        (case_id,)
    ).fetchall()

    promises = conn.execute(
        "SELECT * FROM promises_to_pay WHERE case_id = ? ORDER BY created_timestamp DESC",
        (case_id,)
    ).fetchall()

    payments = conn.execute(
        "SELECT * FROM payments WHERE loan_id = ? ORDER BY payment_date DESC",
        (case["loan_id"],)
    ).fetchall()

    # Prioritization explainability
    score_explain = calculate_case_priority(
        total_arrears=loan["total_arrears"],
        days_past_due=loan["days_past_due"],
        risk_segment=cust["risk_segment"],
        hardship_status=cust["hardship_status"],
        dispute_status=cust["dispute_status"]
    )

    # Next legal contact slot recommendation
    sched_info = compute_next_contact_slot(
        customer=dict(cust),
        contact_pref=dict(pref) if pref else {},
        weekly_attempts_count=case["weekly_attempts_count"]
    )

    conn.close()
    return {
        "case": dict(case),
        "customer": dict(cust),
        "loan": dict(loan),
        "contact_preference": dict(pref) if pref else {},
        "installments": [dict(i) for i in installments],
        "attempts": [dict(a) for a in attempts],
        "promises": [dict(p) for p in promises],
        "payments": [dict(p) for p in payments],
        "explainability": score_explain,
        "scheduling_recommendation": sched_info
    }


@app.post("/api/cases/{case_id}/attempt-contact")
def record_contact_attempt(case_id: str, payload: ContactAttemptRequest):
    """
    Evaluates compliance guardrails before logging an outbound contact attempt.
    Blocks unlawful outreach unless explicitly forced for demonstration.
    """
    conn = get_db_connection()
    case = conn.execute("SELECT * FROM collection_cases WHERE case_id = ?", (case_id,)).fetchone()
    if not case:
        conn.close()
        raise HTTPException(status_code=404, detail="Case not found")

    cust = conn.execute("SELECT * FROM customers WHERE customer_id = ?", (case["customer_id"],)).fetchone()
    pref = conn.execute("SELECT * FROM contact_preferences WHERE customer_id = ?", (case["customer_id"],)).fetchone()

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    if payload.attempt_timestamp_utc:
        try:
            now_utc = datetime.datetime.fromisoformat(payload.attempt_timestamp_utc)
            if now_utc.tzinfo is None:
                now_utc = now_utc.replace(tzinfo=datetime.timezone.utc)
        except Exception:
            pass

    # Fetch active unexpired PTP if any
    active_ptp = None
    if case["active_ptp_id"]:
        ptp_row = conn.execute("SELECT * FROM promises_to_pay WHERE ptp_id = ?", (case["active_ptp_id"],)).fetchone()
        if ptp_row:
            active_ptp = dict(ptp_row)

    # Compliance evaluation
    eval_res = evaluate_contact_compliance(
        customer=dict(cust),
        contact_pref=dict(pref) if pref else {},
        channel=payload.channel,
        attempt_datetime_utc=now_utc,
        recent_7_day_attempts=case["weekly_attempts_count"],
        active_ptp=active_ptp
    )

    if not eval_res["is_compliant"] and not payload.force_override:
        conn.close()
        return {
            "success": False,
            "blocked": True,
            "compliance_status": eval_res["compliance_status"],
            "reason": eval_res["blocking_reason"],
            "rule_triggered": eval_res.get("rule_triggered")
        }

    # Record contact attempt
    att_count = conn.execute("SELECT COUNT(*) as c FROM contact_attempts WHERE case_id = ?", (case_id,)).fetchone()["c"]
    att_id = f"CTP-{case_id}-{att_count + 1:03d}"
    
    qh_info = check_quiet_hours(now_utc, cust["timezone"])
    comp_status = eval_res["compliance_status"] if not payload.force_override else "QUIET_HOURS_VIOLATION"
    outcome = "CONNECTED_PROMISE_MADE" if eval_res["is_compliant"] else "BLOCKED_BY_GUARDRAIL"

    with conn:
        conn.execute(
            """
            INSERT INTO contact_attempts (
                attempt_id, case_id, customer_id, channel, attempt_timestamp,
                customer_local_time, is_permissible_window, rolling_7_day_count,
                compliance_status, contact_outcome, agent_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                att_id, case_id, cust["customer_id"], payload.channel, now_utc.isoformat(),
                qh_info["local_time"], 1 if qh_info["is_permissible"] else 0,
                case["weekly_attempts_count"] + 1, comp_status, outcome, payload.agent_notes
            )
        )
        conn.execute(
            """
            UPDATE collection_cases
            SET total_attempts_count = total_attempts_count + 1,
                weekly_attempts_count = weekly_attempts_count + 1,
                last_contact_date = ?
            WHERE case_id = ?
            """,
            (now_utc.isoformat(), case_id)
        )
        log_audit_event(
            conn, "ContactAttempt", att_id, "OUTBOUND_CONTACT_LOGGED",
            "ANALYST", "OPERATIONS_AGENT", notes=f"Channel: {payload.channel}, Compliance: {comp_status}"
        )

    conn.close()
    return {
        "success": True,
        "blocked": False,
        "attempt_id": att_id,
        "compliance_status": comp_status,
        "customer_local_time": qh_info["local_time"],
        "is_permissible": qh_info["is_permissible"]
    }


@app.post("/api/cases/{case_id}/record-promise")
def record_case_promise(case_id: str, payload: PromiseRequest):
    """Records a Promise to Pay, validates amount against arrears, and pauses active dialer."""
    conn = get_db_connection()
    case = conn.execute("SELECT * FROM collection_cases WHERE case_id = ?", (case_id,)).fetchone()
    if not case:
        conn.close()
        raise HTTPException(status_code=404, detail="Case not found")

    loan = conn.execute("SELECT * FROM loans WHERE loan_id = ?", (case["loan_id"],)).fetchone()
    if payload.promised_amount <= 0:
        conn.close()
        raise HTTPException(status_code=400, detail="Promised amount must be greater than zero")

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    ptp_num = conn.execute("SELECT COUNT(*) as c FROM promises_to_pay").fetchone()["c"] + 1
    ptp_id = f"PTP-2026-{ptp_num:06d}"

    with conn:
        conn.execute(
            """
            INSERT INTO promises_to_pay (
                ptp_id, case_id, loan_id, customer_id, created_timestamp,
                promise_due_date, promised_amount, current_arrears_at_promise,
                ptp_status, fulfilled_amount, fulfillment_date, reconciled_payment_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', 0.0, NULL, NULL)
            """,
            (
                ptp_id, case_id, loan["loan_id"], case["customer_id"], now_iso,
                payload.promise_due_date, payload.promised_amount, loan["total_arrears"]
            )
        )
        # Transition case to PENDING_PTP
        conn.execute(
            """
            UPDATE collection_cases
            SET case_status = 'PENDING_PTP', active_ptp_id = ?
            WHERE case_id = ?
            """,
            (ptp_id, case_id)
        )
        log_audit_event(
            conn, "PromiseToPay", ptp_id, "CREATE_PTP",
            "ANALYST", "OPERATIONS_AGENT",
            notes=f"Promised ${payload.promised_amount} due on {payload.promise_due_date}."
        )

    conn.close()
    return {"success": True, "ptp_id": ptp_id, "status": "PENDING"}


# -------------------------------------------------------------
# 2. Risk & Compliance Reviewer Endpoints
# -------------------------------------------------------------
@app.get("/api/compliance/summary")
def get_compliance_summary():
    """Returns compliance KPI dashboard and violation breakdown."""
    conn = get_db_connection()
    c = conn.cursor()

    total_attempts = c.execute("SELECT COUNT(*) as cnt FROM contact_attempts").fetchone()["cnt"]
    compliant_attempts = c.execute("SELECT COUNT(*) as cnt FROM contact_attempts WHERE compliance_status = 'COMPLIANT'").fetchone()["cnt"]
    violations_count = total_attempts - compliant_attempts

    # Status breakdown
    breakdown = c.execute(
        """
        SELECT compliance_status, COUNT(*) as count
        FROM contact_attempts
        GROUP BY compliance_status
        """
    ).fetchall()

    # Active holds
    hardships = c.execute("SELECT COUNT(*) as cnt FROM customers WHERE hardship_status != 'NONE'").fetchone()["cnt"]
    disputes = c.execute("SELECT COUNT(*) as cnt FROM customers WHERE dispute_status = 'ACTIVE_DISPUTE'").fetchone()["cnt"]
    cease_desist = c.execute("SELECT COUNT(*) as cnt FROM customers WHERE cease_desist_flag = 1").fetchone()["cnt"]

    # Active PTP metrics
    total_ptps = c.execute("SELECT COUNT(*) as cnt FROM promises_to_pay").fetchone()["cnt"]
    kept_ptps = c.execute("SELECT COUNT(*) as cnt FROM promises_to_pay WHERE ptp_status = 'KEPT'").fetchone()["cnt"]
    broken_ptps = c.execute("SELECT COUNT(*) as cnt FROM promises_to_pay WHERE ptp_status = 'BROKEN'").fetchone()["cnt"]
    ptp_success_rate = round((kept_ptps / total_ptps * 100), 1) if total_ptps > 0 else 0.0

    conn.close()
    return {
        "total_attempts": total_attempts,
        "compliant_attempts": compliant_attempts,
        "violations_count": violations_count,
        "compliance_rate_pct": round((compliant_attempts / total_attempts * 100), 2) if total_attempts > 0 else 100.0,
        "status_breakdown": {r["compliance_status"]: r["count"] for r in breakdown},
        "regulatory_holds": {
            "active_hardships": hardships,
            "active_disputes": disputes,
            "cease_and_desist": cease_desist
        },
        "commitment_metrics": {
            "total_ptps": total_ptps,
            "kept": kept_ptps,
            "broken": broken_ptps,
            "fulfillment_rate_pct": ptp_success_rate
        }
    }


@app.get("/api/compliance/anomalies")
def get_anomalies():
    """Runs live scanner across database for the 5 negative scenarios."""
    conn = get_db_connection()
    detected = scan_anomalies(conn)
    conn.close()
    return {"total_detected": len(detected), "anomalies": detected}


@app.post("/api/compliance/remediate")
def remediate_incident(payload: RemediateRequest):
    """Applies instant lawful remediation to a detected anomaly."""
    conn = get_db_connection()
    anomaly_dict = {
        "anomaly_id": payload.anomaly_id,
        "issue_type": payload.issue_type,
        "entity_id": payload.entity_id
    }
    with conn:
        res = remediate_anomaly(conn, anomaly_dict, actor_id=payload.actor_id)
    conn.close()
    return res


@app.get("/api/audit-events")
def get_audit_events(limit: int = 100, offset: int = 0):
    """Retrieves immutable audit trail for full traceability."""
    conn = get_db_connection()
    events = conn.execute(
        "SELECT * FROM audit_events ORDER BY event_timestamp DESC LIMIT ? OFFSET ?",
        (limit, offset)
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) as c FROM audit_events").fetchone()["c"]
    conn.close()
    return {"total": total, "events": [dict(e) for e in events]}


# -------------------------------------------------------------
# 3. Customer / Account Holder Persona Endpoints
# -------------------------------------------------------------
@app.get("/api/customer/{customer_id}/overview")
def get_customer_overview(customer_id: str):
    """Self-service customer portal overview."""
    conn = get_db_connection()
    cust = conn.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,)).fetchone()
    if not cust:
        conn.close()
        raise HTTPException(status_code=404, detail="Customer not found")

    pref = conn.execute("SELECT * FROM contact_preferences WHERE customer_id = ?", (customer_id,)).fetchone()
    loans = conn.execute("SELECT * FROM loans WHERE customer_id = ?", (customer_id,)).fetchall()
    
    loans_data = []
    for l in loans:
        inss = conn.execute(
            "SELECT * FROM installments WHERE loan_id = ? ORDER BY installment_number ASC",
            (l["loan_id"],)
        ).fetchall()
        pmts = conn.execute(
            "SELECT * FROM payments WHERE loan_id = ? ORDER BY payment_date DESC",
            (l["loan_id"],)
        ).fetchall()
        ptps = conn.execute(
            "SELECT * FROM promises_to_pay WHERE loan_id = ? ORDER BY created_timestamp DESC",
            (l["loan_id"],)
        ).fetchall()

        loans_data.append({
            "loan": dict(l),
            "installments": [dict(i) for i in inss],
            "payments": [dict(p) for p in pmts],
            "promises": [dict(p) for p in ptps]
        })

    conn.close()
    return {
        "customer": dict(cust),
        "contact_preference": dict(pref) if pref else {},
        "loans": loans_data
    }


@app.post("/api/customer/{customer_id}/pay")
def customer_submit_payment(customer_id: str, loan_id: str, payload: PaymentRequest):
    """Customer submits a repayment, executed via waterfall allocation."""
    conn = get_db_connection()
    today_str = datetime.date.today().isoformat()
    with conn:
        res = allocate_payment_waterfall(
            conn=conn,
            loan_id=loan_id,
            payment_amount=payload.amount,
            payment_date=today_str,
            payment_method=payload.payment_method,
            ptp_id=payload.ptp_id,
            actor_persona=payload.actor_persona,
            actor_id=customer_id
        )
    conn.close()
    return {"success": True, "result": res}


@app.put("/api/customer/{customer_id}/preferences")
def update_customer_preferences(customer_id: str, payload: CustomerPreferenceUpdate):
    """Customer updates communication channels and permissible contact hours."""
    conn = get_db_connection()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with conn:
        conn.execute(
            """
            UPDATE contact_preferences
            SET preferred_channel = ?, opt_in_phone = ?, opt_in_sms = ?,
                opt_in_email = ?, permissible_start_time = ?, permissible_end_time = ?,
                last_consent_update = ?
            WHERE customer_id = ?
            """,
            (
                payload.preferred_channel, payload.opt_in_phone, payload.opt_in_sms,
                payload.opt_in_email, payload.permissible_start_time, payload.permissible_end_time,
                now_iso, customer_id
            )
        )
        log_audit_event(
            conn, "ContactPreference", customer_id, "UPDATE_PREFERENCES",
            "CUSTOMER", customer_id, notes="Borrower updated contact consents and quiet hours."
        )
    conn.close()
    return {"success": True, "message": "Preferences updated successfully."}


@app.post("/api/customer/{customer_id}/assistance")
def submit_hardship_or_dispute(customer_id: str, payload: HardshipDisputeRequest):
    """Borrower submits formal dispute or hardship assistance request."""
    conn = get_db_connection()
    with conn:
        if payload.action_type == "DISPUTE":
            conn.execute(
                "UPDATE customers SET dispute_status = ? WHERE customer_id = ?",
                (payload.status_value, customer_id)
            )
            # Put active cases on UNDER_DISPUTE
            conn.execute(
                "UPDATE collection_cases SET case_status = 'UNDER_DISPUTE' WHERE customer_id = ?",
                (customer_id,)
            )
        elif payload.action_type == "HARDSHIP":
            conn.execute(
                "UPDATE customers SET hardship_status = ? WHERE customer_id = ?",
                (payload.status_value, customer_id)
            )
            conn.execute(
                "UPDATE collection_cases SET case_status = 'HARDSHIP_HOLD' WHERE customer_id = ?",
                (customer_id,)
            )

        log_audit_event(
            conn, "Customer", customer_id, f"SUBMIT_{payload.action_type}",
            "CUSTOMER", customer_id, notes=payload.notes
        )
    conn.close()
    return {"success": True, "message": f"{payload.action_type} request submitted and collection paused."}


# -------------------------------------------------------------
# 4. System Administrator Endpoints
# -------------------------------------------------------------
@app.get("/api/system/metrics")
def get_system_metrics():
    """Portfolio analytics, roll rates, recovery rate, and queue health."""
    conn = get_db_connection()
    c = conn.cursor()

    total_loans = c.execute("SELECT COUNT(*) as cnt FROM loans").fetchone()["cnt"]
    total_principal = c.execute("SELECT coalesce(SUM(principal_amount), 0.0) as s FROM loans").fetchone()["s"]
    total_balance = c.execute("SELECT coalesce(SUM(current_balance), 0.0) as s FROM loans").fetchone()["s"]
    total_arrears = c.execute("SELECT coalesce(SUM(total_arrears), 0.0) as s FROM loans").fetchone()["s"]
    total_paid = c.execute("SELECT coalesce(SUM(amount), 0.0) as s FROM payments").fetchone()["s"]

    # Roll rate by bucket
    buckets = c.execute(
        """
        SELECT delinquency_bucket, COUNT(*) as count, coalesce(SUM(total_arrears), 0.0) as arrears
        FROM delinquency_snapshots
        GROUP BY delinquency_bucket
        """
    ).fetchall()

    # Cases by priority tier
    tiers = c.execute(
        """
        SELECT priority_tier, COUNT(*) as count, coalesce(SUM(l.total_arrears), 0.0) as arrears
        FROM collection_cases c
        JOIN loans l ON c.loan_id = l.loan_id
        GROUP BY priority_tier
        """
    ).fetchall()

    conn.close()
    return {
        "portfolio": {
            "total_loans": total_loans,
            "total_originated_usd": round(total_principal, 2),
            "current_balance_usd": round(total_balance, 2),
            "total_arrears_usd": round(total_arrears, 2),
            "total_repayments_collected_usd": round(total_paid, 2)
        },
        "delinquency_buckets": [dict(b) for b in buckets],
        "priority_tiers": [dict(t) for t in tiers]
    }


@app.post("/api/system/generate")
def trigger_generation(payload: GenerateRequest):
    """Regenerates dataset on-demand (starter vs full)."""
    db_path = os.path.join(WORKSPACE_DIR, "collections_engine.db")
    init_database(db_path, drop_existing=True)
    
    gen = SyntheticDataGenerator(seed=payload.seed, profile_name=payload.profile)
    counts = gen.generate_all()

    # Export to files and load DB
    out_dir = os.path.join(WORKSPACE_DIR, "exports", payload.profile)
    gen.export_to_files(out_dir)
    
    conn = get_db_connection(db_path)
    gen.export_to_sqlite(conn)
    conn.close()

    return {"success": True, "profile": payload.profile, "seed": payload.seed, "counts": counts}


@app.get("/api/system/validate")
def run_system_validation():
    """Runs the 41-rule validation suite."""
    conn = get_db_connection()
    suite = ValidationSuite(conn)
    res = suite.run_all()
    conn.close()
    return res


# -------------------------------------------------------------
# Static UI Mount
# -------------------------------------------------------------
WEB_DIR = os.path.join(WORKSPACE_DIR, "web")
if os.path.exists(WEB_DIR):
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

@app.get("/")
def serve_index():
    index_file = os.path.join(WEB_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Fair Collections & Recovery Engine API Running"}
