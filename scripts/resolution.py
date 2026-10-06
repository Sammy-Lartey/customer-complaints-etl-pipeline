import pandas as pd
from sqlalchemy.engine import Engine
from ulid import ULID
from sqlalchemy import text

CUSTOMER_COLUMNS = ["number", "name", "gender", "dateOfBirth", "accountType", "branch"]
COMPLAINT_COLUMNS = [
    "number", "location", "region", "logDate", "complaintSource",
    "natureOfComplaint", "subject", "detailsOfComplaint", "comment",
    "updates", "status", "turnaroundTime", "resolutionDate",
    "reasonForReversalRequest", "assign", "nameOfCcRep",
]


def split_silver(df):
    customer_cols = [c for c in CUSTOMER_COLUMNS if c in df.columns]
    complaint_cols = [c for c in COMPLAINT_COLUMNS if c in df.columns]

    customers_df = df[customer_cols].drop_duplicates().reset_index(drop=True)
    complaints_df = df[complaint_cols].copy()

    return customers_df, complaints_df

def build_resolution_key(df):
    keys = df["profileId"].copy()
    fill_from_number = keys.isna() & df["number"].notna()
    keys.loc[fill_from_number] = "number:" + df.loc[fill_from_number, "number"].astype(str)
    return keys


def drop_customers_without_identifiers(customers_df):
    no_identifiers = customers_df["profileId"].isna() & customers_df["number"].isna()
    return customers_df[~no_identifiers]


def filter_orphan_complaints(customers_df, complaints_df):
    return complaints_df[complaints_df["customerId"].isin(customers_df["customerId"])]


def split_rejected_complaints(complaints_df):
    no_identifier = build_resolution_key(complaints_df).isna()
    no_log_date = complaints_df["logDate"].isna()
    rejected = no_identifier | no_log_date

    reasons = pd.Series("", index=complaints_df.index)
    reasons[no_identifier] = "no phone number"
    reasons[no_log_date & ~no_identifier] = "missing logDate"
    reasons[no_log_date & no_identifier] = "no phone number; missing logDate"

    rejected_df = complaints_df[rejected].copy()
    rejected_df["rejectReason"] = reasons[rejected]

    return complaints_df[~rejected], rejected_df


def join_public_client(customers_df, complaints_df, engine):
    client_df = pd.read_sql(
        'SELECT "profileId", "phoneNumber", "phoneNumber2" FROM public.client',
        engine,
    )


    by_phone1 = client_df.set_index("phoneNumber")["profileId"]
    by_phone2 = client_df.dropna(subset=["phoneNumber2"]).set_index("phoneNumber2")["profileId"]
    phone_to_profile = by_phone1.combine_first(by_phone2) if len(by_phone2) else by_phone1

    number2_lookup = client_df.set_index("profileId")["phoneNumber2"]

    customers_df = customers_df.copy()
    customers_df["profileId"] = customers_df["number"].map(phone_to_profile)
    customers_df["number2"] = customers_df["profileId"].map(number2_lookup)

    complaints_df = complaints_df.copy()
    complaints_df["profileId"] = complaints_df["number"].map(phone_to_profile)
    complaints_df["number2"] = complaints_df["profileId"].map(number2_lookup)

    return customers_df, complaints_df


def resolve_customer_ids(customers_df, complaints_df, engine):
    customers_df = customers_df.copy()
    complaints_df = complaints_df.copy()

    customers_df["resolutionKey"] = build_resolution_key(customers_df)
    complaints_df["resolutionKey"] = build_resolution_key(complaints_df)

    customers_df = drop_customers_without_identifiers(customers_df)

    unique_keys = set(customers_df["resolutionKey"].dropna().unique())

    existing = pd.read_sql(
        'SELECT resolution_key, customer_id FROM gold.customer_identity_map',
        engine,
    )
    key_to_ulid = dict(zip(existing["resolution_key"], existing["customer_id"]))

    new_keys = unique_keys - set(key_to_ulid.keys())
    for key in new_keys:
        key_to_ulid[key] = str(ULID())

    if new_keys:
        insert_stmt = text("""
            INSERT INTO gold.customer_identity_map (resolution_key, customer_id)
            VALUES (:resolution_key, :customer_id)
            ON CONFLICT (resolution_key) DO NOTHING
        """)
        with engine.begin() as conn:
            conn.execute(
                insert_stmt,
                [{"resolution_key": k, "customer_id": key_to_ulid[k]} for k in new_keys],
            )

    customers_df["customerId"] = customers_df["resolutionKey"].map(key_to_ulid)
    complaints_df["customerId"] = complaints_df["resolutionKey"].map(key_to_ulid)

    customers_df = customers_df.drop_duplicates(subset=["customerId"])
    complaints_df = filter_orphan_complaints(customers_df, complaints_df)

    customers_df = customers_df.drop(columns=["resolutionKey"])
    complaints_df = complaints_df.drop(columns=["resolutionKey"])

    return customers_df, complaints_df


def run_resolution(silver_path, engine):
    df = pd.read_parquet(silver_path)

    customers_df, complaints_df = split_silver(df)
    customers_df, complaints_df = join_public_client(customers_df, complaints_df, engine)
    complaints_df, rejected_df = split_rejected_complaints(complaints_df)
    customers_df, complaints_df = resolve_customer_ids(customers_df, complaints_df, engine)

    customers_df.to_sql("customers", engine, schema="staging", if_exists="replace", index=False)
    complaints_df.to_sql("complaints", engine, schema="staging", if_exists="replace", index=False)
    rejected_df.to_sql("rejected_complaints", engine, schema="staging", if_exists="replace", index=False)

    return len(customers_df), len(complaints_df), len(rejected_df)