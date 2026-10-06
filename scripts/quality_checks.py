class QualityCheckError(Exception):
    pass


def check_silver_quality(df, bronze_row_count, logger):
    row_drop_pct = (1 - len(df) / bronze_row_count) * 100 if bronze_row_count else 0
    if row_drop_pct > 20:
        logger.warning(
            f"Silver row count dropped {row_drop_pct:.1f}% vs bronze "
            f"({bronze_row_count} -> {len(df)}) -- larger than expected, worth checking"
        )

    for col in ("name", "region"):
        if col in df.columns and df[col].isna().any():
            raise QualityCheckError(
                f"Unexpected nulls in '{col}' after cleaning -- should always have a default value"
            )


def check_resolution_quality(customers_df, logger):
    dup_count = int(customers_df["customerId"].duplicated().sum())
    if dup_count > 0:
        raise QualityCheckError(
            f"{dup_count} duplicate customerId(s) found in resolved customers"
        )


def check_rejected_complaints(rejected_count, loaded_count, logger):
    total = rejected_count + loaded_count

    if rejected_count == 0:
        logger.info(f"0 complaints rejected out of {total}")
        return

    reject_pct = rejected_count / total * 100
    if reject_pct > 20:
        raise QualityCheckError(
            f"{rejected_count} of {total} complaints rejected ({reject_pct:.1f}%) -- "
            f"too many, check the source data. Details in staging.rejected_complaints"
        )

    logger.warning(
        f"{rejected_count} of {total} complaints rejected ({reject_pct:.1f}%) -- "
        f"see staging.rejected_complaints"
    )


def check_gold_quality(customer_count, complaint_count, logger):
    if customer_count == 0:
        raise QualityCheckError("gold.customers loaded with zero rows -- check upstream stages")
    if complaint_count == 0:
        raise QualityCheckError("gold.complaints loaded with zero rows -- check upstream stages")