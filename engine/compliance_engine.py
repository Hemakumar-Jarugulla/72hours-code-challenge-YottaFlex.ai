"""
Compliance and Regulatory Guardrails Engine.
Enforces Fair Debt Collection Practices Act (FDCPA), TCPA, and CFPB Regulation F rules.
"""

import datetime
from typing import Dict, Any, Optional
import zoneinfo


# Permissible contact window defaults (local time of consumer)
DEFAULT_START_TIME = datetime.time(8, 0)   # 8:00 AM
DEFAULT_END_TIME = datetime.time(21, 0)    # 9:00 PM
CFPB_REG_F_WEEKLY_LIMIT = 7                # Max 7 call attempts per 7 consecutive days


def get_consumer_local_time(utc_datetime: datetime.datetime, timezone_str: str) -> datetime.datetime:
    """Converts a UTC datetime to consumer's local timezone."""
    try:
        tz = zoneinfo.ZoneInfo(timezone_str)
    except Exception:
        tz = zoneinfo.ZoneInfo("America/New_York")
    
    if utc_datetime.tzinfo is None:
        utc_datetime = utc_datetime.replace(tzinfo=datetime.timezone.utc)
    return utc_datetime.astimezone(tz)


def check_quiet_hours(
    attempt_datetime_utc: datetime.datetime,
    timezone_str: str,
    pref_start_str: str = "08:00",
    pref_end_str: str = "21:00"
) -> Dict[str, Any]:
    """
    Validates whether the attempt is within permissible hours in the consumer's local timezone.
    FDCPA standard: 08:00 to 21:00.
    """
    local_dt = get_consumer_local_time(attempt_datetime_utc, timezone_str)
    local_time = local_dt.time()
    
    try:
        sh, sm = map(int, pref_start_str.split(":"))
        eh, em = map(int, pref_end_str.split(":"))
        start_time = datetime.time(sh, sm)
        end_time = datetime.time(eh, em)
    except Exception:
        start_time = DEFAULT_START_TIME
        end_time = DEFAULT_END_TIME
        
    is_permissible = start_time <= local_time < end_time
    
    return {
        "is_permissible": is_permissible,
        "local_time": local_time.strftime("%H:%M"),
        "local_datetime_iso": local_dt.isoformat(),
        "permissible_window": f"{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}",
        "reason": "Within permissible local window" if is_permissible else f"Quiet hours violation: Local time {local_time.strftime('%H:%M')} is outside allowed window ({start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')})"
    }


def evaluate_contact_compliance(
    customer: Dict[str, Any],
    contact_pref: Dict[str, Any],
    channel: str,
    attempt_datetime_utc: datetime.datetime,
    recent_7_day_attempts: int,
    active_ptp: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Comprehensive compliance assessment before an outbound outreach can occur.
    Returns:
        is_compliant (bool): True if outreach is lawful and ethical.
        compliance_status (str): Standardized status enum.
        blocking_reason (str): Explanation if blocked.
        details (dict): Diagnostic metadata.
    """
    timezone_str = customer.get("timezone", "America/New_York")
    
    # 1. Cease and Desist Check
    if customer.get("cease_desist_flag", 0) == 1:
        return {
            "is_compliant": False,
            "compliance_status": "CEASE_DESIST_VIOLATION",
            "blocking_reason": "Customer has invoked statutory Cease and Desist. All direct communication is prohibited.",
            "rule_triggered": "FDCPA_SECTION_805_C"
        }

    # 2. Attorney Representation Check
    if customer.get("attorney_represented", 0) == 1:
        return {
            "is_compliant": False,
            "compliance_status": "CEASE_DESIST_VIOLATION",
            "blocking_reason": "Customer is represented by legal counsel. Contact must be directed to attorney only.",
            "rule_triggered": "FDCPA_SECTION_805_A_2"
        }

    # 3. Active Dispute Check (Section 809 validation moratorium)
    if customer.get("dispute_status") == "ACTIVE_DISPUTE":
        return {
            "is_compliant": False,
            "compliance_status": "DISPUTE_HOLD_VIOLATION",
            "blocking_reason": "Debt is under active formal dispute. Collections are frozen pending written debt verification.",
            "rule_triggered": "FDCPA_SECTION_809_B"
        }

    # 4. Hardship Hold Check
    hardship = customer.get("hardship_status", "NONE")
    if hardship in ("TEMPORARY_UNEMPLOYMENT", "MEDICAL_EMERGENCY", "NATURAL_DISASTER"):
        return {
            "is_compliant": False,
            "compliance_status": "HARDSHIP_HOLD_VIOLATION",
            "blocking_reason": f"Customer is registered under active hardship program ({hardship}). Outreach is deferred.",
            "rule_triggered": "CFPB_VULNERABLE_CONSUMER_PROTECTION"
        }

    # 5. Channel Opt-in / Preference Check
    channel_upper = channel.upper()
    if channel_upper == "PHONE" and not contact_pref.get("opt_in_phone", 1):
        return {
            "is_compliant": False,
            "compliance_status": "BLOCKED_BY_GUARDRAIL",
            "blocking_reason": "Consumer has not consented to or has revoked consent for voice phone outreach.",
            "rule_triggered": "TCPA_CONSENT_REVOCATION"
        }
    if channel_upper == "SMS" and not contact_pref.get("opt_in_sms", 1):
        return {
            "is_compliant": False,
            "compliance_status": "BLOCKED_BY_GUARDRAIL",
            "blocking_reason": "Consumer has not consented to or has revoked consent for SMS messaging.",
            "rule_triggered": "TCPA_SMS_CONSENT"
        }
    if channel_upper == "EMAIL" and not contact_pref.get("opt_in_email", 1):
        return {
            "is_compliant": False,
            "compliance_status": "BLOCKED_BY_GUARDRAIL",
            "blocking_reason": "Consumer has unsubscribed from electronic email collection notices.",
            "rule_triggered": "CAN_SPAM_CONSENT"
        }

    # 6. CFPB Regulation F Call Frequency Cap (7-in-7 rule) for telephone calls
    if channel_upper == "PHONE" and recent_7_day_attempts >= CFPB_REG_F_WEEKLY_LIMIT:
        return {
            "is_compliant": False,
            "compliance_status": "FREQUENCY_CAP_EXCEEDED",
            "blocking_reason": f"CFPB Regulation F frequency cap reached: {recent_7_day_attempts} calls in rolling 7-day period (maximum is {CFPB_REG_F_WEEKLY_LIMIT}).",
            "rule_triggered": "CFPB_REG_F_12_CFR_1006_14"
        }

    # 7. Permissible Hours / Quiet Hours Check
    start_str = contact_pref.get("permissible_start_time", "08:00")
    end_str = contact_pref.get("permissible_end_time", "21:00")
    qh = check_quiet_hours(attempt_datetime_utc, timezone_str, start_str, end_str)
    if not qh["is_permissible"]:
        return {
            "is_compliant": False,
            "compliance_status": "QUIET_HOURS_VIOLATION",
            "blocking_reason": qh["reason"],
            "rule_triggered": "FDCPA_SECTION_805_A_1",
            "details": qh
        }

    # 8. Active Promise To Pay Grace Period Check
    if active_ptp and active_ptp.get("ptp_status") == "PENDING":
        # If today is before promise_due_date, defer proactive collection contact
        promise_due = active_ptp.get("promise_due_date")
        if promise_due:
            today_str = attempt_datetime_utc.strftime("%Y-%m-%d")
            if today_str <= promise_due:
                return {
                    "is_compliant": False,
                    "compliance_status": "BLOCKED_BY_GUARDRAIL",
                    "blocking_reason": f"Active Promise to Pay (PTP {active_ptp.get('ptp_id')}) is pending due on {promise_due}. Contact is paused.",
                    "rule_triggered": "FAIR_COMMITMENT_GRACE_POLICY"
                }

    # All checks passed
    return {
        "is_compliant": True,
        "compliance_status": "COMPLIANT",
        "blocking_reason": None,
        "rule_triggered": "ALL_GUARDRAILS_PASSED",
        "details": qh
    }
