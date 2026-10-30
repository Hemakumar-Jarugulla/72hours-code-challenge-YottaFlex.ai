"""
Generator Configuration & Constants.
Defines random seed, scale profiles, distributions, and domain parameters.
"""

DEFAULT_SEED = 20261022

# Scale Profiles: Starter (fast interactive demo & testing) and Full (10,000 loans, 30,000 installments)
SCALE_PROFILES = {
    "starter": {
        "num_customers": 400,
        "num_accounts": 450,
        "num_loans": 500,
        "num_installments_target": 1500,
        "anomaly_counts": {
            "PAID_ACCOUNT_REMAINS_IN_COLLECTION": 5,
            "CONTACT_OUTSIDE_ALLOWED_WINDOW": 8,
            "PAYMENT_ALLOCATED_TO_WRONG_INSTALLMENT": 6,
            "PROMISE_AMOUNT_EXCEEDS_ARREARS": 5,
            "DISPUTED_DEBT_TREATED_AS_CONFIRMED": 6
        }
    },
    "full": {
        "num_customers": 8500,
        "num_accounts": 9200,
        "num_loans": 10000,
        "num_installments_target": 30000,
        "anomaly_counts": {
            "PAID_ACCOUNT_REMAINS_IN_COLLECTION": 50,
            "CONTACT_OUTSIDE_ALLOWED_WINDOW": 80,
            "PAYMENT_ALLOCATED_TO_WRONG_INSTALLMENT": 60,
            "PROMISE_AMOUNT_EXCEEDS_ARREARS": 50,
            "DISPUTED_DEBT_TREATED_AS_CONFIRMED": 60
        }
    }
}

TIMEZONES = [
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles"
]

RISK_SEGMENTS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
RISK_WEIGHTS = [0.45, 0.35, 0.15, 0.05]

HARDSHIP_STATUSES = [
    "NONE",
    "TEMPORARY_UNEMPLOYMENT",
    "MEDICAL_EMERGENCY",
    "NATURAL_DISASTER"
]
HARDSHIP_WEIGHTS = [0.88, 0.06, 0.04, 0.02]

DISPUTE_STATUSES = ["NONE", "ACTIVE_DISPUTE", "RESOLVED"]
DISPUTE_WEIGHTS = [0.93, 0.04, 0.03]

LOAN_TYPES = ["PERSONAL", "AUTO", "MORTGAGE", "SME_REVOLVING"]
LOAN_TYPE_WEIGHTS = [0.50, 0.30, 0.10, 0.10]

CONTACT_CHANNELS = ["PHONE", "SMS", "EMAIL", "PORTAL"]
