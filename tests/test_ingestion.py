import pandas as pd
from ingestion import _stringify_excel_phone


def test_stringify_excel_phone_converts_float():
    assert _stringify_excel_phone(540663527.0) == "540663527"


def test_stringify_excel_phone_keeps_local_string():
    assert _stringify_excel_phone("0540663527") == "0540663527"


def test_stringify_excel_phone_null():
    assert _stringify_excel_phone(None) is None
    assert _stringify_excel_phone(pd.NA) is None
