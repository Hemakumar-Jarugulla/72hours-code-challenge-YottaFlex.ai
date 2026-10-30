"""
Unit Tests for Compliance and Guardrails Engine (FDCPA, TCPA, CFPB Reg F).
"""

import datetime
import pytest
from engine.compliance_engine import (
    evaluate_contact_compliance,
    check_quiet_hours,
    get_consumer_local_time
)


def test_quiet_hours_timezone_conversion():
    # 13:00 UTC = 09:00 AM EDT (America/New_York) -> Allowed
    dt_utc = datetime.datetime(2026, 10, 22, 13, 0, tzinfo=datetime.timezone.utc)
    res_ny = check_quiet_hours(dt_utc, "America/New_York")
    assert res_ny["is_permissible"] is True
    assert res_ny["local_time"] == "09:00"

    # 13:00 UTC = 06:00 AM PDT (America/Los_Angeles) -> Prohibited (before 08:00 AM)
    res_la = check_quiet_hours(dt_utc, "America/Los_Angeles")
    assert res_la["is_permissible"] is False
    assert res_la["local_time"] == "06:00"
    assert "Quiet hours violation" in res_la["reason"]


def test_cfpb_7_in_7_call_frequency_cap():
    customer = {
        "customer_id": "CUST-000001",
        "timezone": "America/New_York",
        "risk_segment": "MEDIUM",
        "hardship_status": "NONE",
        "dispute_status": "NONE",
        "cease_desist_flag": 0,
        "attorney_represented": 0
    }
    contact_pref = {
        "preferred_channel": "PHONE",
        "opt_in_phone": 1,
        "opt_in_sms": 1,
        "opt_in_email": 1,
        "permissible_start_time": "08:00",
        "permissible_end_time": "21:00"
    }
    # 15:00 UTC = 11:00 AM EDT (Permissible window)
    attempt_time = datetime.datetime(2026, 10, 22, 15, 0, tzinfo=datetime.timezone.utc)

    # 6 previous attempts in rolling 7 days -> Allowed
    res_6 = evaluate_contact_compliance(customer, contact_pref, "PHONE", attempt_time, recent_7_day_attempts=6)
    assert res_6["is_compliant"] is True
    assert res_6["compliance_status"] == "COMPLIANT"

    # 7 previous attempts in rolling 7 days -> Blocked by CFPB Reg F
    res_7 = evaluate_contact_compliance(customer, contact_pref, "PHONE", attempt_time, recent_7_day_attempts=7)
    assert res_7["is_compliant"] is False
    assert res_7["compliance_status"] == "FREQUENCY_CAP_EXCEEDED"
    assert "CFPB_REG_F" in res_7["rule_triggered"]


def test_dispute_status_moratorium():
    customer = {
        "customer_id": "CUST-000002",
        "timezone": "America/New_York",
        "dispute_status": "ACTIVE_DISPUTE",
        "hardship_status": "NONE",
        "cease_desist_flag": 0,
        "attorney_represented": 0
    }
    pref = {"opt_in_phone": 1, "permissible_start_time": "08:00", "permissible_end_time": "21:00"}
    dt = datetime.datetime(2026, 10, 22, 15, 0, tzinfo=datetime.timezone.utc)

    res = evaluate_contact_compliance(customer, pref, "PHONE", dt, recent_7_day_attempts=0)
    assert res["is_compliant"] is False
    assert res["compliance_status"] == "DISPUTE_HOLD_VIOLATION"
    assert "FDCPA_SECTION_809" in res["rule_triggered"]


def test_hardship_hold():
    customer = {
        "customer_id": "CUST-000003",
        "timezone": "America/Chicago",
        "dispute_status": "NONE",
        "hardship_status": "MEDICAL_EMERGENCY",
        "cease_desist_flag": 0,
        "attorney_represented": 0
    }
    pref = {"opt_in_phone": 1, "permissible_start_time": "08:00", "permissible_end_time": "21:00"}
    dt = datetime.datetime(2026, 10, 22, 16, 0, tzinfo=datetime.timezone.utc)

    res = evaluate_contact_compliance(customer, pref, "PHONE", dt, recent_7_day_attempts=0)
    assert res["is_compliant"] is False
    assert res["compliance_status"] == "HARDSHIP_HOLD_VIOLATION"


def test_cease_and_desist_and_attorney():
    # Cease & Desist
    c1 = {"customer_id": "C1", "cease_desist_flag": 1, "attorney_represented": 0}
    pref = {}
    dt = datetime.datetime(2026, 10, 22, 15, 0, tzinfo=datetime.timezone.utc)
    res1 = evaluate_contact_compliance(c1, pref, "PHONE", dt, 0)
    assert res1["is_compliant"] is False
    assert res1["compliance_status"] == "CEASE_DESIST_VIOLATION"

    # Attorney Represented
    c2 = {"customer_id": "C2", "cease_desist_flag": 0, "attorney_represented": 1}
    res2 = evaluate_contact_compliance(c2, pref, "PHONE", dt, 0)
    assert res2["is_compliant"] is False
    assert res2["compliance_status"] == "CEASE_DESIST_VIOLATION"


def test_channel_opt_out():
    customer = {"customer_id": "C3", "cease_desist_flag": 0, "attorney_represented": 0, "dispute_status": "NONE", "hardship_status": "NONE", "timezone": "America/New_York"}
    pref = {"opt_in_phone": 0, "opt_in_sms": 1, "opt_in_email": 1, "permissible_start_time": "08:00", "permissible_end_time": "21:00"}
    dt = datetime.datetime(2026, 10, 22, 15, 0, tzinfo=datetime.timezone.utc)

    res = evaluate_contact_compliance(customer, pref, "PHONE", dt, 0)
    assert res["is_compliant"] is False
    assert "TCPA_CONSENT_REVOCATION" in res["rule_triggered"]
