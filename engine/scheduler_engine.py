"""
Lawful Contact Task Scheduler Engine.
Schedules collection contact tasks strictly within legal windows,
respecting consumer timezones, channel consent, and weekly frequency caps.
"""

import datetime
from typing import Dict, Any, Optional
import zoneinfo
from engine.compliance_engine import get_consumer_local_time, check_quiet_hours


DAY_MAP = {
    0: "MON",
    1: "TUE",
    2: "WED",
    3: "THU",
    4: "FRI",
    5: "SAT",
    6: "SUN"
}


def compute_next_contact_slot(
    customer: Dict[str, Any],
    contact_pref: Dict[str, Any],
    reference_utc: Optional[datetime.datetime] = None,
    weekly_attempts_count: int = 0
) -> Dict[str, Any]:
    """
    Calculates the earliest lawful, compliant contact slot for the customer.
    If the customer is under dispute, hardship, or cease-and-desist, scheduling is disabled.
    """
    if reference_utc is None:
        reference_utc = datetime.datetime.now(datetime.timezone.utc)
    elif reference_utc.tzinfo is None:
        reference_utc = reference_utc.replace(tzinfo=datetime.timezone.utc)

    # 1. Hard statutory blocks
    if customer.get("cease_desist_flag", 0) == 1 or customer.get("attorney_represented", 0) == 1:
        return {
            "is_schedulable": False,
            "scheduled_utc": None,
            "scheduled_local": None,
            "recommended_channel": None,
            "reason": "Outbound contact blocked by Cease & Desist or Legal Representation"
        }

    if customer.get("dispute_status") == "ACTIVE_DISPUTE":
        return {
            "is_schedulable": False,
            "scheduled_utc": None,
            "scheduled_local": None,
            "recommended_channel": None,
            "reason": "Debt under active dispute. Scheduling paused pending verification"
        }

    if customer.get("hardship_status", "NONE") != "NONE":
        return {
            "is_schedulable": False,
            "scheduled_utc": None,
            "scheduled_local": None,
            "recommended_channel": None,
            "reason": f"Customer in hardship program ({customer.get('hardship_status')})"
        }

    # 2. Select permissible channel
    preferred_channel = contact_pref.get("preferred_channel", "PHONE").upper()
    recommended_channel = preferred_channel

    # Fallback to permitted channel if preferred is opted-out
    if preferred_channel == "PHONE" and not contact_pref.get("opt_in_phone", 1):
        recommended_channel = "SMS" if contact_pref.get("opt_in_sms", 1) else ("EMAIL" if contact_pref.get("opt_in_email", 1) else None)
    elif preferred_channel == "SMS" and not contact_pref.get("opt_in_sms", 1):
        recommended_channel = "PHONE" if contact_pref.get("opt_in_phone", 1) else ("EMAIL" if contact_pref.get("opt_in_email", 1) else None)
    elif preferred_channel == "EMAIL" and not contact_pref.get("opt_in_email", 1):
        recommended_channel = "PHONE" if contact_pref.get("opt_in_phone", 1) else ("SMS" if contact_pref.get("opt_in_sms", 1) else None)

    if not recommended_channel:
        return {
            "is_schedulable": False,
            "scheduled_utc": None,
            "scheduled_local": None,
            "recommended_channel": None,
            "reason": "Consumer has revoked consent for all digital outreach channels"
        }

    # 3. Check weekly call limit
    if recommended_channel == "PHONE" and weekly_attempts_count >= 7:
        # Advance 24 hours or until rolling window clears
        return {
            "is_schedulable": False,
            "scheduled_utc": None,
            "scheduled_local": None,
            "recommended_channel": "EMAIL" if contact_pref.get("opt_in_email", 1) else None,
            "reason": "CFPB 7-in-7 telephone frequency cap reached. Recommend email notice or deferring."
        }

    # 4. Find next permissible time in consumer local time
    tz_str = customer.get("timezone", "America/New_York")
    try:
        tz = zoneinfo.ZoneInfo(tz_str)
    except Exception:
        tz = zoneinfo.ZoneInfo("America/New_York")

    local_dt = reference_utc.astimezone(tz)
    
    # Parse allowed hours
    start_str = contact_pref.get("permissible_start_time", "08:00")
    end_str = contact_pref.get("permissible_end_time", "21:00")
    sh, sm = map(int, start_str.split(":"))
    eh, em = map(int, end_str.split(":"))
    start_time = datetime.time(sh, sm)
    end_time = datetime.time(eh, em)

    allowed_days = [d.strip().upper() for d in contact_pref.get("allowed_contact_days", "MON,TUE,WED,THU,FRI,SAT").split(",")]

    # Check candidate slot starting today
    candidate_dt = local_dt
    for day_offset in range(7):
        target_date = (local_dt + datetime.timedelta(days=day_offset)).date()
        weekday_name = DAY_MAP[target_date.weekday()]
        
        if weekday_name not in allowed_days:
            continue
            
        # If today, can we call later today?
        if day_offset == 0:
            if candidate_dt.time() < start_time:
                # Slot is at start_time today (e.g. 08:30)
                slot_time = datetime.time(max(sh, 8), max(sm, 30))
                sched_local = datetime.datetime.combine(target_date, slot_time, tzinfo=tz)
                sched_utc = sched_local.astimezone(datetime.timezone.utc)
                return {
                    "is_schedulable": True,
                    "scheduled_utc": sched_utc.isoformat(),
                    "scheduled_local": sched_local.strftime("%Y-%m-%d %H:%M %Z"),
                    "recommended_channel": recommended_channel,
                    "reason": "Scheduled for today during lawful morning window"
                }
            elif candidate_dt.time() < datetime.time(min(eh, 20), 0):
                # We can call in 30 minutes if within window
                tentative = candidate_dt + datetime.timedelta(minutes=30)
                if tentative.time() < end_time:
                    sched_local = tentative
                    sched_utc = sched_local.astimezone(datetime.timezone.utc)
                    return {
                        "is_schedulable": True,
                        "scheduled_utc": sched_utc.isoformat(),
                        "scheduled_local": sched_local.strftime("%Y-%m-%d %H:%M %Z"),
                        "recommended_channel": recommended_channel,
                        "reason": "Scheduled for active business hours today"
                    }
        else:
            # Future day slot at standard morning hour (e.g. 09:30)
            slot_time = datetime.time(9, 30)
            sched_local = datetime.datetime.combine(target_date, slot_time, tzinfo=tz)
            sched_utc = sched_local.astimezone(datetime.timezone.utc)
            return {
                "is_schedulable": True,
                "scheduled_utc": sched_utc.isoformat(),
                "scheduled_local": sched_local.strftime("%Y-%m-%d %H:%M %Z"),
                "recommended_channel": recommended_channel,
                "reason": f"Scheduled for {weekday_name} at lawful local window"
            }

    return {
        "is_schedulable": False,
        "scheduled_utc": None,
        "scheduled_local": None,
        "recommended_channel": None,
        "reason": "No permissible contact window available in the next 7 days"
    }
