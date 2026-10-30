"""
Explainable Prioritization and Account Scoring Engine.
Calculates objective, auditable priority scores and assigns collection tiers
without discriminatory, predatory, or arbitrary rules.
"""

from typing import Dict, Any, Tuple


def calculate_case_priority(
    total_arrears: float,
    days_past_due: int,
    risk_segment: str,
    hardship_status: str = "NONE",
    dispute_status: str = "NONE",
    broken_ptp_count: int = 0,
    kept_ptp_count: int = 0
) -> Dict[str, Any]:
    """
    Computes explainable score (0.0 to 100.0) and assigns priority tier.
    
    Formula components:
    1. Arrears Exposure (0-35 points): Scaled against typical exposure ($5,000 baseline).
    2. Aging / DPD Component (0-35 points): Progressive delinquency buckets.
    3. Credit Risk Segment (0-15 points): Evaluated borrower segment.
    4. Commitment History (-10 to +15 points): Responsiveness to past agreements.
    5. Regulatory Hold Override: If dispute or hardship is active, score is suppressed
       and placed in specialized compliance handling.
    """
    # Check for statutory holds first
    is_held = False
    hold_reason = None
    if dispute_status == "ACTIVE_DISPUTE":
        is_held = True
        hold_reason = "Active Dispute Moratorium (FDCPA Sec 809)"
    elif hardship_status in ("TEMPORARY_UNEMPLOYMENT", "MEDICAL_EMERGENCY", "NATURAL_DISASTER"):
        is_held = True
        hold_reason = f"Vulnerable Consumer Hardship Hold ({hardship_status})"

    # 1. Arrears Component (0 - 35)
    # Monotonically increasing with balance up to $5,000 threshold
    arrears_points = min(35.0, (max(0.0, total_arrears) / 5000.0) * 35.0)

    # 2. Aging / DPD Component (0 - 35)
    if days_past_due <= 0:
        dpd_points = 0.0
    elif days_past_due <= 30:
        dpd_points = 10.0 + (days_past_due / 30.0) * 5.0        # 10.0 - 15.0
    elif days_past_due <= 60:
        dpd_points = 16.0 + ((days_past_due - 30) / 30.0) * 8.0 # 16.0 - 24.0
    elif days_past_due <= 90:
        dpd_points = 25.0 + ((days_past_due - 60) / 30.0) * 5.0 # 25.0 - 30.0
    else:
        dpd_points = 31.0 + min(4.0, ((days_past_due - 90) / 30.0) * 4.0) # 31.0 - 35.0

    # 3. Risk Segment Component (0 - 15)
    segment_weights = {
        "LOW": 2.0,
        "MEDIUM": 6.0,
        "HIGH": 11.0,
        "CRITICAL": 15.0
    }
    risk_points = segment_weights.get(risk_segment.upper(), 6.0)

    # 4. Commitment History Factor (-10 to +15)
    commitment_points = (min(3, broken_ptp_count) * 5.0) - (min(2, kept_ptp_count) * 5.0)

    raw_score = arrears_points + dpd_points + risk_points + commitment_points
    final_score = max(0.0, min(100.0, raw_score))

    # If held due to regulatory reasons, queue urgency is neutral/held
    if is_held:
        effective_score = 0.0
        tier = "P4_LOW"
    else:
        effective_score = round(final_score, 2)
        if effective_score >= 75.0:
            tier = "P1_CRITICAL"
        elif effective_score >= 55.0:
            tier = "P2_HIGH"
        elif effective_score >= 35.0:
            tier = "P3_MEDIUM"
        else:
            tier = "P4_LOW"

    return {
        "priority_score": effective_score,
        "priority_tier": tier,
        "is_held": is_held,
        "hold_reason": hold_reason,
        "explainability": {
            "arrears_exposure_points": round(arrears_points, 2),
            "aging_dpd_points": round(dpd_points, 2),
            "risk_segment_points": round(risk_points, 2),
            "commitment_history_adjustment": round(commitment_points, 2),
            "unclamped_raw_score": round(raw_score, 2),
            "formula": "Score = Arrears(35) + DPD(35) + Risk(15) + PTP_History(±15)"
        }
    }
