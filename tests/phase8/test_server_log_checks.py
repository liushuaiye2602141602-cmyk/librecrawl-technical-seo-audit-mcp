"""Server-log rule and crawl-budget enrichment contracts."""

import pytest

from audit_rules.adapters import DataUnavailableError, PartialExecutionError
from audit_rules.context import PageContext, SiteContext
from audit_rules.registry import load_registry


def _rule(audit_id):
    return next(rule for rule in load_registry() if rule.audit_id == audit_id)


def _logs(**overrides):
    data = {
        "processed_lines": 100, "valid_lines": 100, "malformed_lines": 0,
        "truncated": False, "status_counts": {"200": 95, "404": 5},
        "bot_counts": {"Googlebot": 50}, "url_counts": {"/": 50},
        "bot_url_counts": {"Googlebot|/": 50}, "waste_bot_counts": {},
        "response_time_p95_ms": None, "errors": [],
    }
    data.update(overrides)
    return data


def test_rule_33_records_bot_crawl_baseline():
    from audit_rules.checks.server_logs import check_server_log_analysis
    findings = check_server_log_analysis(
        _rule(33), SiteContext(base_url="https://example.com"), [],
        {"server_logs": _logs()})
    assert len(findings) == 1
    assert findings[0].severity == "Info"
    assert "50 bot requests" in findings[0].detected_value
    assert findings[0].data_source == "Server Logs"


def test_rule_33_flags_server_errors_and_bot_waste():
    from audit_rules.checks.server_logs import check_server_log_analysis
    logs = _logs(
        status_counts={"200": 60, "500": 10},
        bot_counts={"Googlebot": 50},
        waste_bot_counts={"/search?q": 20})
    findings = check_server_log_analysis(
        _rule(33), SiteContext(), [], {"server_logs": logs})
    detected = [finding.detected_value.lower() for finding in findings]
    assert any("5xx" in value for value in detected)
    assert any("waste" in value for value in detected)


def test_rule_33_truncated_or_malformed_evidence_is_partial():
    from audit_rules.checks.server_logs import check_server_log_analysis
    logs = _logs(processed_lines=100, valid_lines=70, malformed_lines=30, truncated=True)
    with pytest.raises(PartialExecutionError) as caught:
        check_server_log_analysis(_rule(33), SiteContext(), [], {"server_logs": logs})
    assert caught.value.findings
    assert "truncated" in str(caught.value).lower()


def test_rule_5_adds_real_bot_hit_frequency_and_stays_partial_without_crawl_stats():
    from audit_rules.checks.foundation_gaps import check_crawl_budget_waste
    pages = [PageContext(url="https://example.com/search?q=term", status_code=200)]
    with pytest.raises(PartialExecutionError) as caught:
        check_crawl_budget_waste(
            _rule(5), SiteContext(), pages,
            {"server_logs": _logs(waste_bot_counts={"/search?q": 25})})
    assert len(caught.value.findings) == 1
    assert "bot_hits=25" in caught.value.findings[0].evidence
    assert "GSC Crawl Stats" in str(caught.value)


def test_server_log_unavailable_never_passes():
    from audit_rules.checks.server_logs import check_server_log_analysis
    with pytest.raises(DataUnavailableError):
        check_server_log_analysis(_rule(33), SiteContext(), [], {})


def test_rule_33_is_registered_partial():
    from audit_rules.adapters import CompatibilityHarness
    registry = load_registry()
    rule = _rule(33)
    assert rule.impl_status.value == "EXISTING_PARTIAL"
    assert rule.required_data_sources == ["Server Logs"]
    assert rule.rule_id in CompatibilityHarness(registry)._adapters
