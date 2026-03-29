from __future__ import annotations

REQUIRED_COLUMNS: set[str] = {
    "timestamp",
    "merchant",
    "mcc",
    "amount",
    "channel",
    "city",
    "country",
}

NUMERIC_FEATURE_COLUMNS: list[str] = [
    "amount",
    "hour",
    "weekday",
    "month",
    "merchant_freq",
    "mcc_freq",
    "merchant_avg",
    "amount_dev",
    "z_amount_merchant",
    "days_since_merchant",
    "is_online",
    "merchant_novelty",
    "hour_dev",
]

CATEGORICAL_FEATURE_COLUMNS: list[str] = ["merchant", "mcc", "city", "country"]

XGB_THRESHOLD: float = 0.65
RF_PERCENTILE: float = 0.95
ANOMALY_ROBUST_Z_THRESHOLD: float = 3.5
ROLLING_WINDOW_MINUTES: int = 10

REVIEW_PRIORITY_LOW: float = 0.45
REVIEW_PRIORITY_HIGH: float = 0.65

RULE_WEIGHTS: dict[str, float] = {
    "rule_geo_jump": 0.25,
    "rule_new_country_high_amt": 0.20,
    "rule_dormant_spike": 0.15,
    "rule_online_rare_spike": 0.15,
    "rule_high_velocity": 0.15,
    # "rule_rare_mcc": 0.10,
}

RULE_TEXT: dict[str, str] = {
    "rule_geo_jump": "Country changed within 60 minutes",
    "rule_new_country_high_amt": "New country + unusually high amount",
    "rule_dormant_spike": "Dormant merchant + amount spike",
    "rule_online_rare_spike": "Online + rare merchant + unusually high amount",
    "rule_high_velocity": "High velocity (3+ txns in 10 minutes)",
    # "rule_rare_mcc": "Rare merchant category (MCC) for this account",
}

TRANSLATION_MAP: dict[str, str] = {
    "num__amount": "Unusual transaction amount",
    "num__amount_dev": "Amount far from typical for this merchant",
    "num__z_amount_merchant": "Amount unusually high for this merchant",
    "num__hour": "Unusual transaction time",
    "num__weekday": "Unusual day of week for spending",
    "num__month": "Out of pattern month",
    "num__merchant_freq": "Merchant rarely used",
    "num__mcc_freq": "Merchant category rarely used",
    "num__merchant_avg": "Amount inconsistent with typical spending at this merchant",
    "num__days_since_merchant": "Merchant not used recently",
    "num__is_online": "Online purchase",
    "num__merchant_novelty": "New or uncommon merchant",
    "num__hour_dev": "Transaction time deviates from usual pattern",
}