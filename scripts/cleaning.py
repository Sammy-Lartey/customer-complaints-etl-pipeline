import os
import re
import unicodedata

import numpy as np
import pandas as pd
from rapidfuzz import process, fuzz

VALID_REGIONS = [
    "Ashanti Region", "Greater Accra Region", "Northern Region", "Volta Region",
    "Central Region", "Western Region", "Upper West Region", "Upper East Region",
    "Oti Region", "Savannah Region", "Bono East Region", "Western North Region",
    "Bono Region", "North East Region", "Ahafo Region", "Eastern Region",
    "Brong Ahafo Region",  # old name, split into Bono/Bono East/Ahafo in 2019 -- kept so old rows aren't lost
]

# short forms that are only ever one region, which fuzzy matching can't tell apart
# from a truly ambiguous input like "Upper"
REGION_ALIASES = {
    "Accra": "Greater Accra Region",
}

# words that follow a name in the assign column to say which team the person is on
TEAM_WORDS = {"cx", "cc", "rep", "operations", "labs", "business", "support"}

# the team stays part of the value for these, since the plain name could be any of their teams
KEEP_TEAM = {"Gideon"}

ASSIGNEE_ALIASES = {"Michale": "Michael"}


def _to_lower_camel(col):
    parts = col.strip().split(" ")
    return parts[0].lower() + "".join(w.title() for w in parts[1:])


def _correct_region(region, threshold=85, margin=5):
    if pd.isna(region) or str(region).strip() == "":
        return "Unknown"

    text = str(region).strip().title()
    if text in VALID_REGIONS:
        return text

    short_name = text[:-len(" Region")] if text.endswith(" Region") else text
    if short_name in REGION_ALIASES:
        return REGION_ALIASES[short_name]

    if not text.endswith("Region"):
        text = text + " Region"

    # token_set_ratio gave a perfect score to any name whose words were a subset
    # of another's, so ties were settled by list order. ratio compares the whole
    # string, and a close runner-up means we don't know -- better Unknown than a guess
    top = process.extract(text, VALID_REGIONS, scorer=fuzz.ratio, limit=2)
    best, best_score, _ = top[0]
    if best_score < threshold or best_score - top[1][1] < margin:
        return "Unknown"
    return best


def _clean_assignee(value):
    if pd.isna(value) or str(value).strip() == "":
        return "Unassigned"

    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    words = text.replace("-", " ").split()

    name = " ".join(w for w in words if w.lower() not in TEAM_WORDS).title()
    team = " ".join(w for w in words if w.lower() in TEAM_WORDS).title()

    if not name:
        return "Unassigned"
    name = ASSIGNEE_ALIASES.get(name, name)
    if name in KEEP_TEAM and team:
        return f"{name}-{team}"
    return name


def format_phone_numbers(series):
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


def load_and_merge_bronze(bronze_dir):
    files = sorted(f for f in os.listdir(bronze_dir) if f.endswith(".parquet"))
    if not files:
        raise FileNotFoundError(f"No bronze parquet files found in {bronze_dir}")
    frames = [pd.read_parquet(os.path.join(bronze_dir, f)) for f in files]

    all_columns = set()
    for df in frames:
        all_columns.update(df.columns)
    for df in frames:
        for col in all_columns:
            if col not in df.columns:
                df[col] = np.nan

    return pd.concat(frames, ignore_index=True)


def clean_columns(df):
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

    if "assign" in df.columns:
        df["assign"] = df["assign"].apply(_clean_assignee)

    if "number" in df.columns:
        df["number"] = format_phone_numbers(df["number"])

    for col in ["logDate", "resolutionDate", "dateOfBirth"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

    df = df.drop_duplicates()
    return df


def validate_and_calculate_tat(df):
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


def run_silver_transform(bronze_dir, silver_path):
    df = load_and_merge_bronze(bronze_dir)
    df = clean_columns(df)

    # these three always get a filler value, so they can't count as real content in a row
    meaningful_cols = [c for c in df.columns if c not in ("name", "region", "assign")]
    df = df[df[meaningful_cols].notna().any(axis=1)]

    df = validate_and_calculate_tat(df)
    df.to_parquet(silver_path, index=False)
    return len(df)