from __future__ import annotations
from typing import List
import numpy as np
import pandas as pd
from app.ml.constants import ROLLING_WINDOW_MINUTES, RULE_TEXT, RULE_WEIGHTS

def engineer_base_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["hour"] = df["timestamp"].dt.hour.fillna(0).astype(int)
    df["weekday"] = df["timestamp"].dt.weekday.fillna(0).astype(int)
    df["month"] = df["timestamp"].dt.month.fillna(1).astype(int)

    df["merchant_freq"] = df.groupby("merchant")["merchant"].transform("count")
    df["mcc_freq"] = df.groupby("mcc")["mcc"].transform("count")

    merchant_avg = df.groupby("merchant")["amount"].transform("mean")
    merchant_std = (
        df.groupby("merchant")["amount"]
        .transform("std")
        .fillna(0.0)
        .replace(0.0, 1.0)
    )

    df["merchant_avg"] = merchant_avg
    df["amount_dev"] = df["amount"] - merchant_avg
    df["z_amount_merchant"] = (df["amount"] - merchant_avg) / merchant_std
    df["z_amount_merchant"] = (
        df["z_amount_merchant"].replace([np.inf, -np.inf], 0.0).fillna(0.0)
    )

    df["last_seen"] = df.groupby("merchant")["timestamp"].shift()
    df["days_since_merchant"] = (df["timestamp"] - df["last_seen"]).dt.days.fillna(-1)

    df["is_online"] = (df["channel"] == "ONLINE").astype(int)
    df["merchant_novelty"] = 1.0 / (df["merchant_freq"] + 1.0)

    merchant_hour_avg = df.groupby("merchant")["hour"].transform("mean")
    df["hour_dev"] = (df["hour"] - merchant_hour_avg).abs()

    df["new_city"] = (df.groupby("city").cumcount() == 0).astype(int)
    df["new_country"] = (df.groupby("country").cumcount() == 0).astype(int)

    df["prev_ts"] = df["timestamp"].shift()
    df["minutes_since_prev"] = (
        (df["timestamp"] - df["prev_ts"]).dt.total_seconds() / 60.0
    ).fillna(1e9)
    df["prev_country"] = df["country"].shift()

    df["txn_count_10m"] = rolling_transaction_counts(df["timestamp"], ROLLING_WINDOW_MINUTES)

    return df

def apply_rule_logic(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    p99_amt = float(df["amount"].quantile(0.99))
    p95_z = float(df["z_amount_merchant"].quantile(0.95))
    p95_amtdev = float(df["amount_dev"].abs().quantile(0.95))

    days_valid = df.loc[df["days_since_merchant"] >= 0, "days_since_merchant"]
    dormant_days = float(days_valid.quantile(0.90)) if not days_valid.empty else 90.0
    dormant_days = max(dormant_days, 30.0)

    rare_merchant_thr = float(df["merchant_freq"].quantile(0.10))
    rare_mcc_thr = float(df["mcc_freq"].quantile(0.10))

    df["rule_geo_jump"] = (
        (df["country"] != df["prev_country"]) &
        (df["minutes_since_prev"] <= 60)
    ).astype(int)

    df["rule_new_country_high_amt"] = (
        (df["new_country"] == 1) &
        (df["amount"] >= p99_amt)
    ).astype(int)

    df["rule_dormant_spike"] = (
        (df["days_since_merchant"] >= dormant_days) &
        (df["amount_dev"].abs() >= p95_amtdev)
    ).astype(int)

    df["rule_online_rare_spike"] = (
        (df["is_online"] == 1) &
        (df["merchant_freq"] <= rare_merchant_thr) &
        (df["z_amount_merchant"] >= p95_z)
    ).astype(int)

    df["rule_high_velocity"] = (df["txn_count_10m"] >= 3).astype(int)
    df["rule_rare_mcc"] = (df["mcc_freq"] <= rare_mcc_thr).astype(int)

    df["rule_risk_raw"] = 0.0
    for column, weight in RULE_WEIGHTS.items():
        df["rule_risk_raw"] += weight * df[column]

    df["rule_risk_score"] = df["rule_risk_raw"].clip(0.0, 1.0)
    df["rule_reasoning"] = df.apply(build_rule_reasoning, axis=1)

    return df

def rolling_transaction_counts(timestamps: pd.Series, window_minutes: int) -> List[int]:
    counts: List[int] = []
    start = 0
    window_seconds = window_minutes * 60

    for i in range(len(timestamps)):
        while (
            start < i
            and (timestamps.iloc[i] - timestamps.iloc[start]).total_seconds() > window_seconds
        ):
            start += 1
        counts.append(i - start + 1)

    return counts

def build_rule_reasoning(row: pd.Series, top_n: int = 3) -> str:
    triggered = [RULE_TEXT[key] for key in RULE_WEIGHTS if int(row.get(key, 0)) == 1]
    return "; ".join(triggered[:top_n]) if triggered else ""