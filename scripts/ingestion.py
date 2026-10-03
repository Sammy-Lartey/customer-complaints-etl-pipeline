import hashlib
import os

import pandas as pd
from sqlalchemy import text


PHONE_COLUMNS = {"NUMBER", "NUMBER2", "number", "number2"}


def _stringify_excel_phone(value):
    if pd.isna(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (int,)):
        return str(value)
    text = str(value).strip()
    return text or None


def _normalize_phone_columns(df):
    for col in df.columns:
        if col in PHONE_COLUMNS:
            df[col] = df[col].map(_stringify_excel_phone)
    return df


def _hash_dataframe(df):
    row_hashes = pd.util.hash_pandas_object(df, index=False).values
    return hashlib.sha256(row_hashes.tobytes()).hexdigest()


def _get_last_known_hash(engine, sheet_name, source_file):
    query = text("""
        SELECT content_hash
        FROM staging.ingestion_log
        WHERE sheet_name = :sheet_name AND source_file = :source_file
        ORDER BY processed_at DESC
        LIMIT 1
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"sheet_name": sheet_name, "source_file": source_file}).fetchone()
    return result[0] if result else None


def _log_ingestion(engine, sheet_name, source_file, content_hash, row_count, bronze_path):
    query = text("""
        INSERT INTO staging.ingestion_log
            (sheet_name, source_file, content_hash, row_count, bronze_path)
        VALUES
            (:sheet_name, :source_file, :content_hash, :row_count, :bronze_path)
        ON CONFLICT (sheet_name, source_file, content_hash) DO NOTHING
    """)
    with engine.begin() as conn:
        conn.execute(query, {
            "sheet_name": sheet_name,
            "source_file": source_file,
            "content_hash": content_hash,
            "row_count": row_count,
            "bronze_path": bronze_path,
        })


def land_changed_sheets(excel_path, bronze_dir,
                         exclude_sheets, engine):
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Source Excel file not found at {excel_path}")

    os.makedirs(bronze_dir, exist_ok=True)

    workbook = pd.ExcelFile(excel_path)
    source_file = os.path.basename(excel_path)
    changed_paths: list[str] = []

    for sheet_name in workbook.sheet_names:
        if sheet_name in exclude_sheets:
            continue

        df = _normalize_phone_columns(workbook.parse(sheet_name))
        if df.empty:
            continue

        current_hash = _hash_dataframe(df)
        last_hash = _get_last_known_hash(engine, sheet_name, source_file)

        if current_hash == last_hash:
            continue

        for col in df.select_dtypes(include="object").columns:
            df[col] = df[col].apply(lambda x: str(x) if pd.notna(x) else None)

        bronze_path = os.path.join(bronze_dir, f"{sheet_name}.parquet")
        df.to_parquet(bronze_path, index=False)

        _log_ingestion(engine, sheet_name, source_file, current_hash, len(df), bronze_path)
        changed_paths.append(bronze_path)

    return changed_paths