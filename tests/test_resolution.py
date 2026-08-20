import pandas as pd
from resolution import (
    split_silver, build_resolution_key,
    drop_customers_without_identifiers, filter_orphan_complaints,
)


def test_build_resolution_key_prefers_profile_id():
    df = pd.DataFrame({
        "profileId": ["ABC123", None],
        "number": ["+233540000000", "+233550000000"],
    })
    result = build_resolution_key(df)
    assert result.iloc[0] == "ABC123"
    assert result.iloc[1] == "number:+233550000000"


def test_drop_customers_without_identifiers():
    df = pd.DataFrame({
        "profileId": ["ABC123", None, None],
        "number": ["+233540000000", "+233550000000", None],
    })
    result = drop_customers_without_identifiers(df)
    # only the third row (no profileId AND no number) should be dropped
    assert len(result) == 2


def test_filter_orphan_complaints_removes_unmatched():
    customers_df = pd.DataFrame({"customerId": ["CUST1", "CUST2"]})
    complaints_df = pd.DataFrame({"customerId": ["CUST1", "CUST2", "CUST_GHOST"]})
    result = filter_orphan_complaints(customers_df, complaints_df)
    assert len(result) == 2
    assert "CUST_GHOST" not in result["customerId"].values


def test_split_silver_separates_customer_and_complaint_columns():
    df = pd.DataFrame({
        "number": ["+233540000000"],
        "name": ["Test Person"],
        "gender": ["Male"],
        "dateOfBirth": ["2000-01-01"],
        "accountType": ["Savings"],
        "branch": ["Accra"],
        "region": ["Greater Accra Region"],
        "status": ["Resolved"],
        "logDate": ["2025-01-01"],
    })
    customers_df, complaints_df = split_silver(df)

    assert "name" in customers_df.columns
    assert "status" not in customers_df.columns
    assert "region" in complaints_df.columns
    assert "name" not in complaints_df.columns