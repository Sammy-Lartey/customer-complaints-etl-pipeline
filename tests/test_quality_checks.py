import pandas as pd
import pytest
from quality_checks import (
    QualityCheckError,
    check_gold_quality,
    check_rejected_complaints,
    check_resolution_quality,
    check_silver_quality,
)


class _DummyLogger:
    def __init__(self):
        self.warnings = []
        self.infos = []

    def warning(self, message):
        self.warnings.append(message)

    def info(self, message):
        self.infos.append(message)


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
    with pytest.raises(QualityCheckError, match="duplicate"):
        check_resolution_quality(customers, logger)


def test_rejected_complaints_logs_info_when_none_rejected():
    logger = _DummyLogger()
    check_rejected_complaints(0, 100, logger)
    assert logger.infos
    assert not logger.warnings


def test_rejected_complaints_warns_on_few_rejects_but_does_not_fail():
    logger = _DummyLogger()
    check_rejected_complaints(2, 98, logger)
    assert logger.warnings


def test_rejected_complaints_fails_above_threshold():
    logger = _DummyLogger()
    with pytest.raises(QualityCheckError, match="rejected"):
        check_rejected_complaints(30, 70, logger)


def test_gold_quality_fails_on_zero_rows():
    logger = _DummyLogger()
    with pytest.raises(QualityCheckError, match="customers"):
        check_gold_quality(0, 10, logger)
    with pytest.raises(QualityCheckError, match="complaints"):
        check_gold_quality(10, 0, logger)