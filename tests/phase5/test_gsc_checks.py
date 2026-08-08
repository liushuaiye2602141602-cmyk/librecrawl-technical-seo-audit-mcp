"""Executable rule contracts for Google Search Console evidence."""

import pytest

from audit_rules.adapters import DataUnavailableError, PartialExecutionError
from audit_rules.context import PageContext, SiteContext
from audit_rules.registry import load_registry


def _rule(audit_id):
    return next(rule for rule in load_registry() if rule.audit_id == audit_id)


def _row(page, query, country="usa", device="MOBILE", **metrics):
    return {
        "page": page, "query": query, "country": country, "device": device,
        "clicks": metrics.get("clicks", 0),
        "impressions": metrics.get("impressions", 0),
        "ctr": metrics.get("ctr", 0), "position": metrics.get("position", 0),
    }


def test_rule_44_flags_google_selected_canonical_mismatch():
    from audit_rules.checks.gsc import check_google_selected_canonical

    pages = [PageContext(
        url="https://example.com/a", status_code=200,
        canonical_url="https://example.com/a",
        gsc_data={"inspection": {
            "verdict": "PASS", "userCanonical": "https://example.com/a",
            "googleCanonical": "https://example.com/b",
        }},
    )]
    findings = check_google_selected_canonical(
        _rule(44), SiteContext(), pages,
        {"gsc": {"inspection_attempted": 1, "inspection_succeeded": 1}},
    )

    assert len(findings) == 1
    assert findings[0].detected_value == "Google canonical: https://example.com/b"
    assert findings[0].data_source == "GSC API"


def test_rule_44_preserves_findings_when_inspection_is_partial():
    from audit_rules.checks.gsc import check_google_selected_canonical

    pages = [PageContext(
        url="https://example.com/a", status_code=200,
        gsc_data={"inspection": {"userCanonical": "https://example.com/a",
                                  "googleCanonical": "https://example.com/b"}},
    )]
    with pytest.raises(PartialExecutionError) as caught:
        check_google_selected_canonical(
            _rule(44), SiteContext(), pages,
            {"gsc": {"inspection_attempted": 2, "inspection_succeeded": 1}},
        )
    assert len(caught.value.findings) == 1
    assert "1/2" in str(caught.value)


def test_rule_52_detects_query_served_by_multiple_pages():
    from audit_rules.checks.gsc import check_keyword_cannibalization

    data = {"gsc": {"current_rows": [
        _row("https://example.com/a", "blue widget", impressions=80, clicks=8),
        _row("https://example.com/b", "blue widget", impressions=40, clicks=3),
        _row("https://example.com/c", "unique query", impressions=100, clicks=9),
    ], "errors": []}}
    findings = check_keyword_cannibalization(_rule(52), SiteContext(), [], data)

    assert len(findings) == 1
    assert findings[0].detected_value == "2 ranking pages for query 'blue widget'"


def test_rule_75_detects_material_device_or_country_position_gap():
    from audit_rules.checks.gsc import check_device_country_ranking

    data = {"gsc": {"current_rows": [
        _row("https://example.com/a", "widget", "usa", "DESKTOP",
             impressions=100, position=4),
        _row("https://example.com/a", "widget", "usa", "MOBILE",
             impressions=100, position=11),
        _row("https://example.com/a", "widget", "gbr", "DESKTOP",
             impressions=100, position=5),
    ], "errors": []}}
    findings = check_device_country_ranking(_rule(75), SiteContext(), [], data)

    assert findings
    assert any("device" in finding.detected_value.lower() for finding in findings)


def test_rule_76_maps_declining_query_to_page():
    from audit_rules.checks.gsc import check_declining_page_keyword_map

    current = [_row("https://example.com/a", "widget", impressions=80, clicks=4)]
    previous = [_row("https://example.com/a", "widget", impressions=120, clicks=10)]
    findings = check_declining_page_keyword_map(
        _rule(76), SiteContext(), [],
        {"gsc": {"current_rows": current, "previous_rows": previous, "errors": []}},
    )

    assert len(findings) == 1
    assert findings[0].url == "https://example.com/a"
    assert "widget" in findings[0].detected_value
    assert "60.0%" in findings[0].detected_value


@pytest.mark.parametrize(
    ("audit_id", "function_name"),
    [(44, "check_google_selected_canonical"), (52, "check_keyword_cannibalization"),
     (75, "check_device_country_ranking"), (76, "check_declining_page_keyword_map")],
)
def test_gsc_rules_raise_unavailable_instead_of_passing(audit_id, function_name):
    from audit_rules.checks import gsc

    with pytest.raises(DataUnavailableError):
        getattr(gsc, function_name)(_rule(audit_id), SiteContext(), [], {})


def test_registry_marks_implemented_gsc_rules_as_partial_and_gsc_sufficient():
    rules = {rule.audit_id: rule for rule in load_registry()}
    for audit_id in (44, 52, 75, 76):
        assert rules[audit_id].impl_status.value == "EXISTING_PARTIAL"
        assert rules[audit_id].required_data_sources == ["GSC API"]
