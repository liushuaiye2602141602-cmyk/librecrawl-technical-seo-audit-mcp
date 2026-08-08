"""Production registration and honest PageSpeed provider semantics."""

from __future__ import annotations

from audit_rules.categories import ExecutionStatus, ResultStatus
from audit_rules.providers.performance_snapshot import PerformanceSnapshot


def _export(page_count: int = 1) -> dict:
    return {
        "site_check": {},
        "pages": [
            {
                "url": f"https://example.com/page-{index}",
                "status_code": 200,
                "title": f"Page {index}",
                "meta_description": "Description",
                "h1": "Heading",
                "canonical_url": f"https://example.com/page-{index}",
                "robots": "index, follow",
                "word_count": 300,
                "internal_links_count": 1,
            }
            for index in range(page_count)
        ],
        "links": [],
    }


def _coverage(rows, audit_id: int):
    return next(row for row in rows if row.audit_id == audit_id)


def _success(url: str) -> PerformanceSnapshot:
    return PerformanceSnapshot(
        url=url,
        requested_url=url,
        strategy="mobile",
        psi_status="success",
        field_data_available=True,
        field_data_scope="URL",
        field_lcp_ms=1800,
        field_inp_ms=120,
        field_cls=0.05,
        lab_performance_score=90,
        lab_lcp_ms=1900,
    )


def _error(url: str) -> PerformanceSnapshot:
    return PerformanceSnapshot(
        url=url,
        requested_url=url,
        strategy="mobile",
        psi_status="error",
        error="PSI rate limit exceeded (HTTP 429)",
    )


def test_provider_uses_registry_canonical_name():
    from audit_rules.providers.pagespeed_provider import PageSpeedDataProvider

    assert PageSpeedDataProvider(api_key="test").name == "PageSpeed API"


def test_integration_runner_registers_pagespeed_provider(monkeypatch):
    from audit_rules import integration
    from audit_rules.providers.pagespeed_provider import PageSpeedDataProvider

    monkeypatch.delenv("PAGESPEED_API_KEY", raising=False)
    integration.reset_runner_cache()
    runner = integration._get_runner()

    assert set(runner.providers) == {
        "PageSpeed API", "GSC API", "Semrush API", "GA4 API", "Server Logs",
        "WordPress Privileged"}
    assert isinstance(runner.providers["PageSpeed API"], PageSpeedDataProvider)
    assert runner.providers["PageSpeed API"].is_available() is False


def test_invalid_runtime_config_falls_back_safely():
    from audit_rules.providers.pagespeed_provider import (
        _parse_sample_limit,
        _parse_strategies,
    )

    assert _parse_sample_limit("not-an-int") == 20
    assert _parse_sample_limit("0") == 20
    assert _parse_sample_limit("500") == 100
    assert _parse_strategies("desktop,mobile,desktop") == ["desktop", "mobile"]
    assert _parse_strategies("tablet,watch") == ["mobile"]


def test_all_psi_errors_are_not_checked_unknown(monkeypatch):
    from audit_rules.providers.pagespeed_provider import PageSpeedDataProvider
    from audit_rules.registry import load_registry
    from audit_rules.runner import RuleRunner

    provider = PageSpeedDataProvider(api_key="test", sample_limit=2)
    provider._available = True
    monkeypatch.setattr(provider, "_fetch_snapshot", lambda url, strategy: _error(url))
    runner = RuleRunner(load_registry(), providers={"PageSpeed API": provider})

    _, rows = runner.run_from_export(_export(2), "https://example.com")
    row = _coverage(rows, 19)

    assert row.execution_status == ExecutionStatus.NOT_CHECKED
    assert row.result_status == ResultStatus.UNKNOWN
    assert row.not_checked_reason == "Data source unavailable: PageSpeed API"


def test_one_success_keeps_provider_available(monkeypatch):
    from audit_rules.providers.pagespeed_provider import PageSpeedDataProvider
    from audit_rules.registry import load_registry
    from audit_rules.runner import RuleRunner

    provider = PageSpeedDataProvider(api_key="test", sample_limit=2)
    provider._available = True
    calls = {"count": 0}

    def fetch(url, strategy):
        calls["count"] += 1
        return _success(url) if calls["count"] == 1 else _error(url)

    monkeypatch.setattr(provider, "_fetch_snapshot", fetch)
    runner = RuleRunner(load_registry(), providers={"PageSpeed API": provider})

    _, rows = runner.run_from_export(_export(2), "https://example.com")
    row = _coverage(rows, 19)

    assert row.execution_status != ExecutionStatus.NOT_CHECKED
    assert "PageSpeed API" not in row.not_checked_reason
