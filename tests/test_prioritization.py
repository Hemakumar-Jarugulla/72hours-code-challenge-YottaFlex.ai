"""
Unit Tests for Prioritization & Scoring Engine.
"""

import pytest
from engine.prioritization_engine import calculate_case_priority


def test_priority_score_calculation_components():
    # High arrears ($4,000) and 75 DPD and CRITICAL risk
    res = calculate_case_priority(
        total_arrears=4000.0,
        days_past_due=75,
        risk_segment="CRITICAL",
        hardship_status="NONE",
        dispute_status="NONE",
        broken_ptp_count=1,
        kept_ptp_count=0
    )

    score = res["priority_score"]
    tier = res["priority_tier"]
    explain = res["explainability"]

    # Arrears: (4000/5000)*35 = 28.0
    assert explain["arrears_exposure_points"] == 28.0
    # DPD: 61-90 bucket -> 25 + (15/30)*5 = 27.5
    assert explain["aging_dpd_points"] == 27.5
    # Risk segment: CRITICAL = 15.0
    assert explain["risk_segment_points"] == 15.0
    # Commitment: 1 broken = +5.0
    assert explain["commitment_history_adjustment"] == 5.0
    # Total = 28.0 + 27.5 + 15.0 + 5.0 = 75.5
    assert score == 75.5
    assert tier == "P1_CRITICAL"


def test_priority_low_tier():
    # Low arrears ($200), 10 DPD, LOW risk
    res = calculate_case_priority(
        total_arrears=200.0,
        days_past_due=10,
        risk_segment="LOW",
        hardship_status="NONE",
        dispute_status="NONE",
        broken_ptp_count=0,
        kept_ptp_count=1
    )
    assert res["priority_tier"] == "P4_LOW"
    assert res["priority_score"] < 35.0


def test_priority_regulatory_hold_override():
    # Customer under active dispute should be placed on hold
    res = calculate_case_priority(
        total_arrears=5000.0,
        days_past_due=95,
        risk_segment="CRITICAL",
        dispute_status="ACTIVE_DISPUTE"
    )
    assert res["is_held"] is True
    assert res["priority_score"] == 0.0
    assert "Dispute" in res["hold_reason"]
