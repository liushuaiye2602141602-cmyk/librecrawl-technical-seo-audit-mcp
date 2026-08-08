"""Semrush-backed rule contracts."""

import pytest

from audit_rules.adapters import DataUnavailableError, PartialExecutionError
from audit_rules.context import PageContext, SiteContext
from audit_rules.registry import load_registry


def _rule(audit_id):
    return next(rule for rule in load_registry() if rule.audit_id == audit_id)


def test_rule_31_records_backlink_overview_as_auditable_info():
    from audit_rules.checks.semrush import check_backlink_overview

    findings = check_backlink_overview(
        _rule(31), SiteContext(base_url="https://example.com"), [],
        {"semrush": {"overview": {
            "backlinks_count": 120, "domains_count": 30, "score": 55,
            "new_count": 8, "lost_count": 3, "follows_count": 90},
            "errors": []}},
    )
    assert len(findings) == 1
    assert findings[0].severity == "Info"
    assert "30 referring domains" in findings[0].detected_value
    assert findings[0].data_source == "Semrush API"


def test_rule_31_zero_referring_domains_is_opportunity():
    from audit_rules.checks.semrush import check_backlink_overview

    finding = check_backlink_overview(
        _rule(31), SiteContext(), [],
        {"semrush": {"overview": {"backlinks_count": 0, "domains_count": 0},
                     "errors": []}},)[0]
    assert finding.severity == "Opportunity"


def test_rule_77_flags_authoritative_followed_lost_link_to_crawled_page():
    from audit_rules.checks.semrush import check_lost_backlinks

    pages = [PageContext(url="https://example.com/product", status_code=200)]
    data = {"semrush": {"lost_links": [
        {"source_url": "https://authority.example/guide",
         "target_url": "https://example.com/product", "domain_score": 70,
         "page_score": 50, "anchor": "product", "is_lost": True,
         "is_nofollow": False, "last_seen_at": "2026-07-01T00:00:00"},
        {"source_url": "https://weak.example/a",
         "target_url": "https://example.com/product", "domain_score": 5,
         "is_lost": True, "is_nofollow": False},
    ], "lost_total": 2, "lost_truncated": False, "errors": []}}
    findings = check_lost_backlinks(_rule(77), SiteContext(), pages, data)

    assert len(findings) == 1
    assert findings[0].url == "https://example.com/product"
    assert "authority.example" in findings[0].evidence


def test_rule_77_truncation_preserves_findings_as_partial():
    from audit_rules.checks.semrush import check_lost_backlinks

    pages = [PageContext(url="https://example.com/a", status_code=200)]
    data = {"semrush": {"lost_links": [{
        "source_url": "https://ref.example/a", "target_url": "https://example.com/a",
        "domain_score": 40, "is_lost": True, "is_nofollow": False}],
        "lost_total": 1000, "lost_truncated": True, "errors": []}}
    with pytest.raises(PartialExecutionError) as caught:
        check_lost_backlinks(_rule(77), SiteContext(), pages, data)
    assert len(caught.value.findings) == 1
    assert "truncated" in str(caught.value).lower()


@pytest.mark.parametrize(
    ("audit_id", "function_name"),
    [(31, "check_backlink_overview"), (77, "check_lost_backlinks")],
)
def test_semrush_unavailable_never_passes(audit_id, function_name):
    from audit_rules.checks import semrush

    with pytest.raises(DataUnavailableError):
        getattr(semrush, function_name)(_rule(audit_id), SiteContext(), [], {})


def test_semrush_rules_are_registered_partial_rules():
    from audit_rules.adapters import CompatibilityHarness

    registry = load_registry()
    harness = CompatibilityHarness(registry)
    rules = {rule.audit_id: rule for rule in registry}
    for audit_id in (31, 77):
        assert rules[audit_id].impl_status.value == "EXISTING_PARTIAL"
        assert rules[audit_id].required_data_sources == ["Semrush API"]
        assert rules[audit_id].rule_id in harness._adapters
