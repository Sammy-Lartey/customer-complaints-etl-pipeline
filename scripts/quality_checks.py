import pandas as pd


def check_silver_quality(df: pd.DataFrame, bronze_row_count: int, logger) -> None:
    row_drop_pct = (1 - len(df) / bronze_row_count) * 100 if bronze_row_count else 0
    if row_drop_pct > 20:
        logger.warning(
            f"Silver row count dropped {row_drop_pct:.1f}% vs bronze "
            f"({bronze_row_count} -> {len(df)}) -- larger than expected, worth checking"
        )

    for col in ("name", "region"):
        if col in df.columns and df[col].isna().any():
            logger.warning(f"Unexpected nulls in '{col}' after cleaning -- should always have a default value")


def check_resolution_quality(customers_df: pd.DataFrame, complaints_df: pd.DataFrame, logger) -> None:
    dup_count = customers_df["customerId"].duplicated().sum()
    if dup_count > 0:
        logger.warning(f"{dup_count} duplicate customerId(s) found in resolved customers")

    orphan_count = (~complaints_df["customerId"].isin(customers_df["customerId"])).sum()
    if orphan_count > 0:
        logger.warning(f"{orphan_count} complaint(s) reference a customerId with no matching customer")


def check_gold_quality(customer_count: int, complaint_count: int, logger) -> None:
    if customer_count == 0:
        logger.warning("gold.customers loaded with zero rows -- check upstream stages")
    if complaint_count == 0:
        logger.warning("gold.complaints loaded with zero rows -- check upstream stages")