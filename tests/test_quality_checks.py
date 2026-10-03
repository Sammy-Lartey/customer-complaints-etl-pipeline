import pandas as pd
import pytest
from quality_checks import (
    QualityCheckError,
    check_gold_quality,
    check_resolution_quality,
    check_silver_quality,
)


class _DummyLogger:
    def __init__(self):
        self.warnings = []

    def warning(self, message):
        self.warnings.append(message)


def test_silver_quality_warns_on_large_drop_but_does_not_fail():
    logger = _DummyLogger()
    df = pd.DataFrame({"name": ["Ama"], "region": ["Ashanti Region"]})
    check_silver_quality(df, bronze_row_count=10, logger=logger)
    assert logger.warnings


def test_silver_quality_fails_on_null_name():
    logger = _DummyLogger()
    df = pd.DataFrame({"name": [None], "region": ["Ashanti Region"]})
    with pytest.raises(QualityCheckError, match="name"):
        check_silver_quality(df, bronze_row_count=1, logger=logger)


def test_resolution_quality_fails_on_duplicate_customer_ids():
    logger = _DummyLogger()
    customers = pd.DataFrame({"customerId": ["A", "A"]})
    complaints = pd.DataFrame({"customerId": ["A"]})
    with pytest.raises(QualityCheckError, match="duplicate"):
        check_resolution_quality(customers, complaints, logger)


def test_resolution_quality_fails_on_orphan_complaints():
    logger = _DummyLogger()
    customers = pd.DataFrame({"customerId": ["A"]})
    complaints = pd.DataFrame({"customerId": ["A", "GHOST"]})
    with pytest.raises(QualityCheckError, match="no matching customer"):
        check_resolution_quality(customers, complaints, logger)


def test_gold_quality_fails_on_zero_rows():
    logger = _DummyLogger()
    with pytest.raises(QualityCheckError, match="customers"):
        check_gold_quality(0, 10, logger)
    with pytest.raises(QualityCheckError, match="complaints"):
        check_gold_quality(10, 0, logger)
