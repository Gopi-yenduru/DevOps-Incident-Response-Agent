"""
Tests for the keyword-based severity pre-filter in routers.logs.

This heuristic runs before the LLM and decides which logs get queued for the
agent pipeline, so its classification boundaries matter.
"""

from routers.logs import classify_log_severity


def test_fatal_is_critical_anomaly():
    severity, is_anomaly = classify_log_severity(
        "2024-01-15 FATAL: PostgreSQL primary failover initiated"
    )
    assert severity == "critical"
    assert is_anomaly is True


def test_error_keyword_is_error_anomaly():
    severity, is_anomaly = classify_log_severity(
        "ERROR: NullPointerException at AuthController.validateToken line 142"
    )
    assert severity == "error"
    assert is_anomaly is True


def test_warning_keyword_is_warning_anomaly():
    severity, is_anomaly = classify_log_severity(
        "WARNING: request timeout after 30s, retrying"
    )
    assert severity == "warning"
    assert is_anomaly is True


def test_normal_info_log_is_not_anomaly():
    severity, is_anomaly = classify_log_severity(
        "INFO: Successfully processed 1247 requests, avg 45ms"
    )
    assert severity == "normal"
    assert is_anomaly is False


def test_classification_is_case_insensitive():
    severity, is_anomaly = classify_log_severity("fatal: kernel panic")
    assert severity == "critical"
    assert is_anomaly is True


def test_critical_takes_precedence_over_error():
    # Line contains both an error-tier and a critical-tier keyword;
    # critical must win because it is checked first.
    severity, _ = classify_log_severity("ERROR and FATAL both present")
    assert severity == "critical"
