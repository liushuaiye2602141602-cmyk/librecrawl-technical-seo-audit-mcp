"""A rule may PASS only when its adapter actually completed."""

from __future__ import annotations

from audit_rules.categories import ExecutionStatus, ResultStatus
from audit_rules.context import PageContext, SiteContext


def _export() -> dict:
    return {
        "site_check": {
            "sitemap": {"found": True, "url_count": 1},
            "https_redirect": {"redirects": True},
        },
        "pages": [
            {
                "url": "https://example.com/",
                "status_code": 200,
                "title": "A unique and useful example page title",
                "meta_description": "Description",
                "h1": "Example",
                "canonical_url": "https://example.com/",
                "robots": "index, follow",
                "word_count": 300,
            }
        ],
        "links": [],
    }


def test_unregistered_partial_rule_is_not_false_pass():
    from audit_rules.adapters import CompatibilityHarness
    from audit_rules.registry import load_registry
    from audit_rules.runner import RuleRunner

    registry = load_registry()
    harness = CompatibilityHarness(registry)
    harness._adapters.pop("audit_deliverables")
    _, rows = RuleRunner(registry, harness=harness).run_from_export(
        _export(), "https://example.com"
    )
    rule40 = next(row for row in rows if row.audit_id == 40)

    assert rule40.execution_status == ExecutionStatus.NOT_CHECKED
    assert rule40.result_status == ResultStatus.UNKNOWN
    assert rule40.not_checked_reason == "No registered adapter executed"


def test_adapter_exception_is_recorded_without_sensitive_detail(monkeypatch):
    from audit_rules.adapters import CompatibilityHarness
    from audit_rules.registry import load_registry

    harness = CompatibilityHarness(load_registry())

    def broken(*args, **kwargs):
        raise RuntimeError("secret backend detail")

    monkeypatch.setitem(harness._adapters, "robots_txt_exists", broken)
    harness.run(
        SiteContext(base_url="https://example.com"),
        [PageContext(url="https://example.com", status_code=200)],
        {},
    )

    assert 1 not in harness.completed_rule_ids
    assert harness.not_checked_reasons[1] == "Adapter failed (RuntimeError)"
    assert "secret" not in harness.not_checked_reasons[1]


def test_explicit_data_unavailable_reason_is_preserved(monkeypatch):
    from audit_rules.adapters import CompatibilityHarness, DataUnavailableError
    from audit_rules.registry import load_registry

    harness = CompatibilityHarness(load_registry())

    def unavailable(*args, **kwargs):
        raise DataUnavailableError("Response headers absent from crawl export")

    monkeypatch.setitem(harness._adapters, "robots_txt_exists", unavailable)
    harness.run(
        SiteContext(base_url="https://example.com"),
        [PageContext(url="https://example.com", status_code=200)],
        {},
    )

    assert harness.not_checked_reasons[1] == "Response headers absent from crawl export"


def test_coverage_uses_harness_execution_reason():
    from audit_rules.coverage import CoverageManager
    from audit_rules.registry import load_registry

    registry = load_registry()
    rows = CoverageManager(registry).compute(
        SiteContext(base_url="https://example.com"),
        [PageContext(url="https://example.com", status_code=200)],
        [],
        providers_available={"LibreCrawl"},
        executed_rule_ids=set(),
        not_checked_reasons={40: "Deliverable pipeline unavailable"},
    )
    rule40 = next(row for row in rows if row.audit_id == 40)

    assert rule40.execution_status == ExecutionStatus.NOT_CHECKED
    assert rule40.result_status == ResultStatus.UNKNOWN
    assert rule40.not_checked_reason == "Deliverable pipeline unavailable"
