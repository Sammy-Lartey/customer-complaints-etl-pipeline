import os
import re

import numpy as np
import pandas as pd
from rapidfuzz import process, fuzz

VALID_REGIONS = [
    "Ashanti Region", "Greater Accra Region", "Northern Region", "Volta Region",
    "Central Region", "Western Region", "Upper West Region", "Upper East Region",
    "Oti Region", "Savannah Region", "Bono East Region", "Western North Region",
    "Brong Ahafo Region", "North East Region", "Ahafo Region", "Eastern Region",
]


def _to_lower_camel(col: str) -> str:
    parts = col.strip().split(" ")
    return parts[0].lower() + "".join(w.title() for w in parts[1:])


def _correct_region(region, threshold=80):
    if pd.isna(region) or str(region).strip() == "":
        return "Unknown"
    match, score, _ = process.extractOne(region, VALID_REGIONS, scorer=fuzz.token_set_ratio)
    return match if score >= threshold else "Unknown"


def format_phone_numbers(series: pd.Series) -> pd.Series:
    digits = series.astype(str).str.replace(r"\D", "", regex=True)
    formatted = pd.Series(np.nan, index=series.index, dtype="object")
    formatted[digits.str.startswith("0") & (digits.str.len() == 10)] = (
        "+233" + digits.str[1:]
    )
    formatted[digits.str.startswith("233") & (digits.str.len() == 12)] = (
        "+" + digits
    )
    formatted[digits.str.len() == 9] = "+233" + digits
    return formatted


def load_and_merge_bronze(bronze_dir: str) -> pd.DataFrame:
    files = [f for f in os.listdir(bronze_dir) if f.endswith(".parquet")]
    frames = [pd.read_parquet(os.path.join(bronze_dir, f)) for f in files]

    all_columns = set()
    for df in frames:
        all_columns.update(df.columns)
    for df in frames:
        for col in all_columns:
            if col not in df.columns:
                df[col] = np.nan

    return pd.concat(frames, ignore_index=True)


def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "NAME" in df.columns:
        df["NAME"] = df["NAME"].apply(
            lambda x: "Unknown" if pd.isna(x) or str(x).strip().lower() in ("nan", "none", "null", "")
            else str(x).strip()
        )

    df.columns = [_to_lower_camel(c) for c in df.columns]
    df.columns = df.columns.str.replace(" ", "", regex=False)

    rename_map = {}
    if "tat" in df.columns:
        rename_map["tat"] = "turnaroundTime"
    if "dob" in df.columns:
        rename_map["dob"] = "dateOfBirth"
    df = df.rename(columns=rename_map)

    if "turnaroundTime" in df.columns:
        df["turnaroundTime"] = pd.to_numeric(df["turnaroundTime"], errors="coerce").astype("Int64")
    if "dateOfBirth" in df.columns:
        df["dateOfBirth"] = pd.to_datetime(df["dateOfBirth"], errors="coerce")

    # vectorized: strip whitespace across all text columns at once
    text_cols = df.select_dtypes(include="object").columns
    for col in text_cols:
        df[col] = df[col].str.strip()

    # vectorized title-case, excluding ID/phone-like columns
    exclude = {"number", "number2", "branch", "customerId", "profileId"}
    for col in [c for c in text_cols if c not in exclude]:
        df[col] = df[col].str.title()

    # region correction stays row-wise -- rapidfuzz.process.extractOne has
    # no vectorized equivalent, this is an inherently per-value operation
    if "region" in df.columns:
        df["region"] = df["region"].apply(_correct_region)

    if "number" in df.columns:
        df["number"] = format_phone_numbers(df["number"])

    for col in ["logDate", "resolutionDate", "dateOfBirth"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

    df = df.drop_duplicates()
    return df


def validate_and_calculate_tat(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["logDate"] = pd.to_datetime(df["logDate"], errors="coerce")
    df["resolutionDate"] = pd.to_datetime(df["resolutionDate"], errors="coerce")

    negative = df["turnaroundTime"] < 0
    swapped = df["logDate"].notna() & df["resolutionDate"].notna() & (df["logDate"] > df["resolutionDate"])

    fix = negative & swapped
    if fix.any():
        temp = df.loc[fix, "logDate"].copy()
        df.loc[fix, "logDate"] = df.loc[fix, "resolutionDate"]
        df.loc[fix, "resolutionDate"] = temp
        df.loc[fix, "turnaroundTime"] = (df.loc[fix, "resolutionDate"] - df.loc[fix, "logDate"]).dt.days

    still_neg = df["turnaroundTime"] < 0
    valid_dates = df["logDate"].notna() & df["resolutionDate"].notna() & (df["resolutionDate"] >= df["logDate"])
    recalc = still_neg & valid_dates
    if recalc.any():
        df.loc[recalc, "turnaroundTime"] = (df.loc[recalc, "resolutionDate"] - df.loc[recalc, "logDate"]).dt.days

    missing_fix = valid_dates & df["turnaroundTime"].isna()
    if missing_fix.any():
        df.loc[missing_fix, "turnaroundTime"] = (df.loc[missing_fix, "resolutionDate"] - df.loc[missing_fix, "logDate"]).dt.days

    return df


def run_silver_transform(bronze_dir: str, silver_path: str) -> int:
    df = load_and_merge_bronze(bronze_dir)
    df = clean_columns(df)

    meaningful_cols = [c for c in df.columns if c not in ("name", "region")]
    df = df[df[meaningful_cols].notna().any(axis=1)]

    df = validate_and_calculate_tat(df)
    df.to_parquet(silver_path, index=False)
    return len(df)