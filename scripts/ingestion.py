import hashlib
import os

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine


def _hash_dataframe(df: pd.DataFrame) -> str:
    row_hashes = pd.util.hash_pandas_object(df, index=True).values
    return hashlib.sha256(row_hashes.tobytes()).hexdigest()


def _get_last_known_hash(engine: Engine, sheet_name: str, source_file: str) -> str | None:
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


def _log_ingestion(engine: Engine, sheet_name: str, source_file: str,
                    content_hash: str, row_count: int, bronze_path: str) -> None:
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


def land_changed_sheets(excel_path: str, bronze_dir: str,
                         exclude_sheets: list[str], engine: Engine) -> list[str]:
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Source Excel file not found at {excel_path}")

    os.makedirs(bronze_dir, exist_ok=True)

    workbook = pd.ExcelFile(excel_path)
    source_file = os.path.basename(excel_path)
    changed_paths: list[str] = []

    for sheet_name in workbook.sheet_names:
        if sheet_name in exclude_sheets:
            continue

        df = workbook.parse(sheet_name)
        if df.empty:
            continue

        current_hash = _hash_dataframe(df)
        last_hash = _get_last_known_hash(engine, sheet_name, source_file)

        if current_hash == last_hash:
            continue

        bronze_path = os.path.join(bronze_dir, f"{sheet_name}.parquet")
        for col in df.select_dtypes(include="object").columns:
            df[col] = df[col].apply(lambda x: str(x) if pd.notna(x) else None)

        bronze_path = os.path.join(bronze_dir, f"{sheet_name}.parquet")
        df.to_parquet(bronze_path, index=False)

        _log_ingestion(engine, sheet_name, source_file, current_hash, len(df), bronze_path)
        changed_paths.append(bronze_path)

    return changed_paths