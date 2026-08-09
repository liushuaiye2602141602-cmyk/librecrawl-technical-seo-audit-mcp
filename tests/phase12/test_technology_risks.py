"""Task F — TechnologyRiskCorrelator."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _profile_with(technology="WordPress", confidence="High", status="DETECTED"):
    from audit_rules.technology.models import TechnologyDetection
    from audit_rules.technology.models import TechnologyEvidence
    evidence = TechnologyEvidence(
        signal_type="meta_generator", signal_value=technology,
        source_url="https://example.com/", source_scope="single_page",
        strength="strong")
    detection = TechnologyDetection(
        category="CMS", technology_name=technology,
        technology_type="CMS", detection_sources=[evidence],
        confidence_score=0.9, confidence=confidence, status=status)
    return {"detections": [detection.__dict__]}


def test_technology_detected_is_not_automatic_risk():
    from audit_rules.technology.risks import TechnologyRiskCorrelator
    risks = TechnologyRiskCorrelator().correlate(_profile_with())
    assert risks
    assert all(r.classification == "CONFIRMED_OBSERVATION" for r in risks)
    assert all(r.observation["is_risk"] is False for r in risks)


def test_technology_risk_maps_to_existing_rule():
    from audit_rules.technology.risks import TechnologyRiskCorrelator
    risks = TechnologyRiskCorrelator().correlate(_profile_with("WordPress"))
    wordpress = next(r for r in risks if r.technology == "WordPress")
    assert 36 in wordpress.mapped_audit_ids
    assert 64 in wordpress.mapped_audit_ids


def test_technology_risk_does_not_double_penalize():
    from audit_rules.technology.risks import TechnologyRiskCorrelator
    from audit_rules.coverage import CoverageManager
    from audit_rules.registry import load_registry
    from audit_rules.scoring import compute_audit_score
    from audit_rules.context import SiteContext

    rows = CoverageManager(load_registry()).compute(
        SiteContext(base_url="https://example.com/"), [], [],
        providers_available={"LibreCrawl"})
    base_score = compute_audit_score([], rows).overall_score
    risks = TechnologyRiskCorrelator().correlate(_profile_with("WordPress"))
    # Correlation must be metadata-only: no Finding, no score mutation.
    assert risks
    assert compute_audit_score([], rows).overall_score == base_score


def test_no_new_rule_created_by_risk_correlator():
    from audit_rules.registry import load_registry
    assert len(load_registry()) == 80


def test_no_risk_when_no_mapping_applies():
    from audit_rules.technology.risks import TechnologyRiskCorrelator
    risks = TechnologyRiskCorrelator().correlate(
        _profile_with("jQuery"))
    assert risks == []


def test_confirmed_risk_only_when_mapped_audit_has_finding():
    from audit_rules.technology.risks import TechnologyRiskCorrelator
    from audit_rules.coverage import CoverageManager
    from audit_rules.registry import load_registry
    from audit_rules.context import SiteContext

    rows = CoverageManager(load_registry()).compute(
        SiteContext(base_url="https://example.com/",
                    site_profile="wordpress_remote"), [], [],
        providers_available={"LibreCrawl"},
        executed_rule_ids={40},
    )
    correlator = TechnologyRiskCorrelator()
    risks = correlator.correlate(_profile_with("WordPress"))
    wordpress = next(r for r in risks if r.technology == "WordPress")
    assert wordpress.mapped_audit_ids
    confirmed = correlator.confirmed_risk(wordpress, rows)
    assert confirmed is False  # no mapped rule has a confirmed FAIL/WARNING
    assert wordpress.classification == "CONFIRMED_OBSERVATION"


def test_confirmed_risk_true_when_mapped_rule_fails():
    from audit_rules.technology.risks import TechnologyRiskCorrelator
    from audit_rules.coverage import CoverageManager
    from audit_rules.registry import load_registry
    from audit_rules.context import SiteContext
    from audit_rules.adapters import _mk_finding

    rule = next(r for r in load_registry() if r.audit_id == 36)
    finding = _mk_finding(rule, url="https://example.com/",
                          detected="WP privileged check not available",
                          expected="evidence", evidence="none")
    rows = CoverageManager(load_registry()).compute(
        SiteContext(base_url="https://example.com/",
                    site_profile="wordpress_remote"), [], [finding],
        providers_available={"LibreCrawl", "WordPress Privileged"},
        executed_rule_ids={36, 40},
    )
    wordpress = next(
        r for r in TechnologyRiskCorrelator().correlate(
            _profile_with("WordPress"))
        if r.technology == "WordPress")
    assert TechnologyRiskCorrelator().confirmed_risk(wordpress, rows) is True
