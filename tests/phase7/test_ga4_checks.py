"""GA4-backed configuration and conversion rule contracts."""

from datetime import date, timedelta

import pytest

from audit_rules.adapters import DataUnavailableError, PartialExecutionError
from audit_rules.context import SiteContext
from audit_rules.registry import load_registry


def _rule(audit_id):
    return next(rule for rule in load_registry() if rule.audit_id == audit_id)


def _healthy_ga4():
    start = date(2026, 7, 9)
    return {
        "property": {"name": "properties/123", "displayName": "Example", "deleteTime": ""},
        "key_events": [{"eventName": "generate_lead"}],
        "event_counts": {"page_view": 500, "generate_lead": 5},
        "daily_activity": [
            {"date": (start + timedelta(days=i)).strftime("%Y%m%d"),
             "sessions": 10, "totalUsers": 8} for i in range(28)],
        "errors": [],
    }


def test_rule_34_healthy_api_evidence_is_still_partial_for_bing_and_tag_duplication():
    from audit_rules.checks.ga4 import check_gsc_ga4_config

    data = {"ga4": _healthy_ga4(), "gsc": {"sitemaps": [], "errors": []}}
    with pytest.raises(PartialExecutionError) as caught:
        check_gsc_ga4_config(_rule(34), SiteContext(), [], data)
    assert caught.value.findings == []
    assert "Bing" in str(caught.value)


def test_rule_34_flags_trashed_property_and_missing_daily_data():
    from audit_rules.checks.ga4 import check_gsc_ga4_config

    ga4 = _healthy_ga4()
    ga4["property"]["deleteTime"] = "2026-08-01T00:00:00Z"
    ga4["daily_activity"] = []
    with pytest.raises(PartialExecutionError) as caught:
        check_gsc_ga4_config(
            _rule(34), SiteContext(), [],
            {"ga4": ga4, "gsc": {"sitemaps": [], "errors": []}})
    detected = [finding.detected_value for finding in caught.value.findings]
    assert any("trashed" in value.lower() for value in detected)
    assert any("no sessions" in value.lower() for value in detected)


def test_rule_35_flags_missing_key_events_and_zero_observed_key_event():
    from audit_rules.checks.ga4 import check_event_conversion_tracking

    ga4 = _healthy_ga4()
    ga4["event_counts"]["generate_lead"] = 0
    with pytest.raises(PartialExecutionError) as caught:
        check_event_conversion_tracking(_rule(35), SiteContext(), [], {"ga4": ga4})
    assert len(caught.value.findings) == 1
    assert "generate_lead" in caught.value.findings[0].detected_value

    ga4["key_events"] = []
    with pytest.raises(PartialExecutionError) as caught:
        check_event_conversion_tracking(_rule(35), SiteContext(), [], {"ga4": ga4})
    assert "No GA4 key events" in caught.value.findings[0].detected_value


@pytest.mark.parametrize(
    ("audit_id", "function_name"),
    [(34, "check_gsc_ga4_config"), (35, "check_event_conversion_tracking")],
)
def test_ga4_unavailable_never_passes(audit_id, function_name):
    from audit_rules.checks import ga4
    with pytest.raises(DataUnavailableError):
        getattr(ga4, function_name)(_rule(audit_id), SiteContext(), [], {})


def test_ga4_rules_are_partial_and_registered():
    from audit_rules.adapters import CompatibilityHarness
    registry = load_registry()
    harness = CompatibilityHarness(registry)
    rules = {rule.audit_id: rule for rule in registry}
    assert rules[34].required_data_sources == ["GSC API", "GA4 API"]
    assert rules[35].required_data_sources == ["GA4 API"]
    for audit_id in (34, 35):
        assert rules[audit_id].impl_status.value == "EXISTING_PARTIAL"
        assert rules[audit_id].rule_id in harness._adapters
