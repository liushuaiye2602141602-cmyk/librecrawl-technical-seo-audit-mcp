"""Rules 46, 48, and 80 external evidence evaluation contracts."""

import pytest

from audit_rules.adapters import DataUnavailableError, PartialExecutionError
from audit_rules.context import SiteContext
from audit_rules.registry import load_registry


def _rule(audit_id):
    return next(rule for rule in load_registry() if rule.audit_id == audit_id)


def _page(**overrides):
    item = {
        "url": "https://example.com/products",
        "raw_text_chars": 1000, "rendered_text_chars": 1000,
        "raw_internal_links": 10, "rendered_internal_links": 10,
        "initial_items": 12, "after_scroll_items": 12,
        "load_more_requires_interaction": False,
        "crawlable_pagination_fallback": True,
        "lazy_images_without_fallback": 0,
    }
    item.update(overrides)
    return item


def test_rule_46_flags_material_render_only_text_and_links():
    from audit_rules.checks.external_snapshots import check_js_rendered_content

    with pytest.raises(PartialExecutionError) as caught:
        check_js_rendered_content(
            _rule(46), SiteContext(), [], {"render_snapshot": {
                "pages": [_page(rendered_text_chars=2000, rendered_internal_links=25)],
                "errors": [],
            }})
    detected = " ".join(item.detected_value for item in caught.value.findings)
    assert "render-only text" in detected
    assert "render-only internal links" in detected
    assert all(item.data_source == "Rendered DOM Snapshot" for item in caught.value.findings)


def test_rule_48_flags_interaction_dependency_and_lazy_image_fallbacks():
    from audit_rules.checks.external_snapshots import check_lazy_load_indexability

    with pytest.raises(PartialExecutionError) as caught:
        check_lazy_load_indexability(
            _rule(48), SiteContext(), [], {"render_snapshot": {
                "pages": [_page(
                    after_scroll_items=36, load_more_requires_interaction=True,
                    crawlable_pagination_fallback=False,
                    lazy_images_without_fallback=4)], "errors": []}})
    assert len(caught.value.findings) == 2
    assert any("fallback" in item.detected_value.lower() for item in caught.value.findings)


def test_render_rules_stay_partial_even_when_sample_has_no_issues():
    from audit_rules.checks.external_snapshots import (
        check_js_rendered_content, check_lazy_load_indexability,
    )

    for audit_id, check in ((46, check_js_rendered_content), (48, check_lazy_load_indexability)):
        with pytest.raises(PartialExecutionError) as caught:
            check(_rule(audit_id), SiteContext(), [], {
                "render_snapshot": {"pages": [_page()], "errors": []}})
        assert caught.value.findings == []
        assert "sample" in str(caught.value).lower()


def _availability(**overrides):
    endpoint = {
        "url": "https://example.com/", "total_checks": 2016,
        "failed_checks": 0, "five_xx_checks": 0,
        "availability_pct": 100.0, "p95_ms": 800.0, "locations": 3,
    }
    endpoint.update(overrides.pop("endpoint", {}))
    data = {"window_hours": 168, "endpoints": [endpoint], "errors": []}
    data.update(overrides)
    return data


def test_rule_80_flags_5xx_low_availability_and_high_latency():
    from audit_rules.checks.external_snapshots import check_availability_5xx_monitoring

    findings = check_availability_5xx_monitoring(
        _rule(80), SiteContext(), [], {"availability_snapshot": _availability(
            endpoint={"failed_checks": 5, "five_xx_checks": 3,
                      "availability_pct": 99.7, "p95_ms": 3500})})
    assert len(findings) == 3
    assert all(item.data_source == "Availability Monitor" for item in findings)


def test_rule_80_requires_week_and_two_locations_for_full_pass():
    from audit_rules.checks.external_snapshots import check_availability_5xx_monitoring

    with pytest.raises(PartialExecutionError) as caught:
        check_availability_5xx_monitoring(
            _rule(80), SiteContext(), [], {"availability_snapshot": _availability(
                window_hours=24, endpoint={"locations": 1})})
    assert caught.value.findings == []
    assert "168" in str(caught.value)


@pytest.mark.parametrize("audit_id,check_name,key", [
    (46, "check_js_rendered_content", "render_snapshot"),
    (48, "check_lazy_load_indexability", "render_snapshot"),
    (80, "check_availability_5xx_monitoring", "availability_snapshot"),
])
def test_missing_external_snapshot_never_passes(audit_id, check_name, key):
    from audit_rules.checks import external_snapshots

    with pytest.raises(DataUnavailableError):
        getattr(external_snapshots, check_name)(_rule(audit_id), SiteContext(), [], {})
    with pytest.raises(DataUnavailableError):
        getattr(external_snapshots, check_name)(
            _rule(audit_id), SiteContext(), [], {key: {"errors": ["bad"]}})


def test_remaining_external_rules_are_registered_and_migrated():
    from audit_rules.adapters import CompatibilityHarness

    registry = load_registry()
    harness = CompatibilityHarness(registry)
    for audit_id, source in ((46, "Rendered DOM Snapshot"),
                             (48, "Rendered DOM Snapshot"),
                             (80, "Availability Monitor")):
        rule = _rule(audit_id)
        assert rule.impl_status.value == "EXISTING_PARTIAL"
        assert rule.required_data_sources == [source]
        assert rule.rule_id in harness._adapters
    assert len(harness._adapters) == 72
    assert not [r for r in registry if r.impl_status.value == "NEW_EXTERNAL_DATA"]
