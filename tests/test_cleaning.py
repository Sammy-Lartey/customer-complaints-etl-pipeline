import pandas as pd
from cleaning import _correct_region, _to_lower_camel, format_phone_numbers, validate_and_calculate_tat


def test_correct_region_exact_match():
    assert _correct_region("Greater Accra Region") == "Greater Accra Region"


def test_correct_region_fuzzy_match():
    # common real-world typo/shorthand should still resolve correctly
    assert _correct_region("Greater Accra") == "Greater Accra Region"


def test_correct_region_garbage_input():
    assert _correct_region("Not A Real Place") == "Unknown"


def test_correct_region_missing_value():
    assert _correct_region(None) == "Unknown"


def test_to_lower_camel_multi_word():
    assert _to_lower_camel("NATURE OF COMPLAINT") == "natureOfComplaint"


def test_to_lower_camel_single_word():
    assert _to_lower_camel("NAME") == "name"


def test_format_phone_numbers_leading_zero():
    result = format_phone_numbers(pd.Series(["0540663527"]))
    assert result.iloc[0] == "+233540663527"


def test_format_phone_numbers_already_233():
    result = format_phone_numbers(pd.Series(["233540663527"]))
    assert result.iloc[0] == "+233540663527"


def test_format_phone_numbers_nine_digits():
    result = format_phone_numbers(pd.Series(["540663527"]))
    assert result.iloc[0] == "+233540663527"


def test_format_phone_numbers_invalid_stays_null():
    result = format_phone_numbers(pd.Series(["123"]))
    assert pd.isna(result.iloc[0])


def test_validate_and_calculate_tat_swaps_reversed_dates():
    df = pd.DataFrame({
        "logDate": ["2025-03-10"],
        "resolutionDate": ["2025-03-05"],  # earlier than logDate -- reversed
        "turnaroundTime": [-5],
    })
    result = validate_and_calculate_tat(df)
    # after the swap, logDate should be the earlier date
    assert result["logDate"].iloc[0] < result["resolutionDate"].iloc[0]
    assert result["turnaroundTime"].iloc[0] == 5


def test_validate_and_calculate_tat_fills_missing():
    df = pd.DataFrame({
        "logDate": ["2025-03-01"],
        "resolutionDate": ["2025-03-04"],
        "turnaroundTime": [None],
    })
    result = validate_and_calculate_tat(df)
    assert result["turnaroundTime"].iloc[0] == 3