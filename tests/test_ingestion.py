import pandas as pd
import pytest

from ingestion import REQUIRED_COLUMNS, SourceSchemaError, check_source_columns, find_missing_columns


def _frame(columns):
    return pd.DataFrame({c: [1] for c in columns})


def test_find_missing_columns_all_present():
    assert find_missing_columns(REQUIRED_COLUMNS) == []


def test_find_missing_columns_ignores_case_and_spaces():
    # the real workbook has headers like 'LOG DATE ' with a trailing space
    assert find_missing_columns(["LOG DATE ", "name", " Number", "Resolution Date", "tat"]) == []


def test_find_missing_columns_reports_what_is_missing_in_order():
    assert find_missing_columns(["NAME", "NUMBER"]) == ["LOG DATE", "RESOLUTION DATE", "TAT"]


def test_find_missing_columns_extra_columns_are_fine():
    assert find_missing_columns(REQUIRED_COLUMNS + ["MONTH", "EDUCATION", "AGE"]) == []


def test_check_source_columns_passes_when_all_sheets_ok():
    frames = {"January": _frame(REQUIRED_COLUMNS), "February": _frame(REQUIRED_COLUMNS)}
    check_source_columns(frames)


def test_check_source_columns_names_the_sheet_and_column():
    frames = {"March": _frame(["NAME", "NUMBER", "LOG DATE", "RESOLUTION DATE"])}
    with pytest.raises(SourceSchemaError) as err:
        check_source_columns(frames)
    assert "March" in str(err.value)
    assert "TAT" in str(err.value)


def test_check_source_columns_reports_every_bad_sheet():
    frames = {
        "January": _frame(REQUIRED_COLUMNS),
        "March": _frame(["NAME", "NUMBER"]),
        "April": _frame(["TAT"]),
    }
    with pytest.raises(SourceSchemaError) as err:
        check_source_columns(frames)
    assert "March" in str(err.value)
    assert "April" in str(err.value)
    assert "January" not in str(err.value)