"""Utility functions for applying barcode misuse heuristics."""
from __future__ import annotations

from typing import List
from datetime import datetime, timedelta

import pandas as pd

REQUIRED_COLS = [
    "Timestamp",
    "Operator_ID",
    "Location",
    "Device_ID",
    "Test_Type",
]

PII_COLUMNS = {"Name", "Result", "MRN", "DOB"}

TIME_FORMATS = [
    "%d/%m/%Y %H:%M",
    "%Y-%m-%d %H:%M",
]


def parse_timestamp(value: str) -> datetime | None:
    """Attempt to parse a timestamp string with multiple formats."""
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def validate_dataframe(df: pd.DataFrame) -> list[str]:
    """Validate dataframe columns and parse timestamps."""
    errors: list[str] = []

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        errors.append(f"Missing required columns: {missing}")

    pii_found = [c for c in df.columns if c in PII_COLUMNS]
    if pii_found:
        errors.append(f"PII columns detected: {pii_found}")

    if "Timestamp" in df.columns:
        parsed = df["Timestamp"].apply(lambda x: parse_timestamp(str(x)))
        if parsed.isna().any():
            errors.append("Failed to parse some timestamps")
        df["Timestamp"] = parsed

    return errors


def compute_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Apply flagging logic to a validated dataframe."""
    df = df.copy()
    df.sort_values(["Operator_ID", "Timestamp"], inplace=True)

    df["Event_ID"] = range(1, len(df) + 1)
    df["Prev_Timestamp"] = df.groupby("Operator_ID")["Timestamp"].shift()
    df["Prev_Location"] = df.groupby("Operator_ID")["Location"].shift()
    df["Prev_Device"] = df.groupby("Operator_ID")["Device_ID"].shift()

    df["Time_Diff"] = (
        df["Timestamp"] - df["Prev_Timestamp"]
    ).dt.total_seconds() / 60.0

    # RAPID flag
    df["RAPID"] = df["Time_Diff"] < 1

    # LOC_CONFLICT flag
    df["LOC_CONFLICT"] = (
        (df["Location"] != df["Prev_Location"]) & (df["Time_Diff"] <= 5)
    )

    # DEVICE_HOP flag
    window = 10
    df["DEVICE_HOP"] = False
    for op, group in df.groupby("Operator_ID"):
        times = group["Timestamp"]
        devices = group["Device_ID"].tolist()
        for idx, current_time in enumerate(times):
            start = current_time - timedelta(minutes=window)
            subset = group[
                (group["Timestamp"] >= start)
                & (group["Timestamp"] <= current_time)
            ]
            if subset["Device_ID"].nunique() >= 3:
                df.loc[subset.index, "DEVICE_HOP"] = True

    # SHIFT_VIOL flag
    df["SHIFT_VIOL"] = False
    for op, group in df.groupby("Operator_ID"):
        times = group["Timestamp"].tolist()
        for i, t in enumerate(times):
            start = t - timedelta(hours=24)
            end_subset = group[(group["Timestamp"] >= start) & (group["Timestamp"] <= t)]
            # difference between earliest and latest within 24h window
            if (t - end_subset["Timestamp"].min()).total_seconds() / 3600 > 14:
                df.loc[end_subset.index, "SHIFT_VIOL"] = True

    # LOAD_DEV flag
    df["Hour"] = df["Timestamp"].dt.floor("H")
    hourly_counts = (
        df.groupby(["Operator_ID", "Hour"]).size().rename("Hour_Count")
    )
    df = df.join(hourly_counts, on=["Operator_ID", "Hour"])
    df["LOAD_DEV"] = df["Hour_Count"] > 20

    # COLOC flag
    coloc_counts = df.groupby(["Device_ID", "Hour"])\
        ["Operator_ID"].nunique().rename("User_Count")
    df = df.join(coloc_counts, on=["Device_ID", "Hour"])
    df["COLOC"] = df["User_Count"] >= 3

    df["FLAGGED"] = df[[
        "RAPID",
        "LOC_CONFLICT",
        "DEVICE_HOP",
        "SHIFT_VIOL",
        "LOAD_DEV",
        "COLOC",
    ]].any(axis=1)

    return df


def build_hourly_matrix(df: pd.DataFrame) -> dict:
    """Return nested dict {operator: {hour: count}}."""
    heat = (
        df.groupby([df["Operator_ID"], df["Timestamp"].dt.hour])
        .size()
        .unstack(fill_value=0)
    )
    return {
        str(op): {str(h): int(heat.loc[op, h]) for h in heat.columns}
        for op in heat.index
    }
