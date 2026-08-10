"""Task E — CMS/applicability bridge (confidence gate, no auto-PASS)."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _profile_with_wordpress(confidence="High", status="DETECTED",
                            strong_count=2):
    sources = [
        {"signal_type": "meta_generator", "signal_value": "WordPress",
         "source_url": "https://example.com/", "source_scope": "single_page",
         "strength": "strong", "provenance": "local_crawl"},
        {"signal_type": "asset_path", "signal_value": "/wp-content/",
         "source_url": "https://example.com/", "source_scope": "single_page",
         "strength": "strong", "provenance": "local_crawl"},
    ][:strong_count]
    return {
        "detections": [{
            "category": "CMS", "technology_name": "WordPress",
            "technology_type": "CMS", "status": status,
            "confidence": confidence, "confidence_score": 0.9,
            "detection_sources": sources,
        }],
    }


def _site(profile="generic"):
    from audit_rules.context import SiteContext
    return SiteContext(base_url="https://example.com/",
                       site_profile=profile)


def _coverage_row(audit_id, site_ctx, executed=None):
    from audit_rules.coverage import CoverageManager
    from audit_rules.registry import load_registry
    rows = CoverageManager(load_registry()).compute(
        site_ctx, [], [],
        providers_available={"LibreCrawl"},
        executed_rule_ids=executed or set(),
    )
    return next(r for r in rows if r.audit_id == audit_id)


def test_cms_detection_controls_rule_applicability():
    row = _coverage_row(36, _site(profile="wordpress_remote"))
    assert row.execution_status.value != "NOT_APPLICABLE"


def test_wordpress_detection_does_not_auto_pass_privileged_rules():
    row = _coverage_row(36, _site(profile="wordpress_remote"))
    assert row.result_status.value != "PASS"


def test_low_confidence_cms_does_not_drive_applicability():
    from audit_rules.technology.applicability import cms_applicability_decision
    profile = _profile_with_wordpress(confidence="Low")
    assert cms_applicability_decision(profile) == "generic"


def test_medium_confidence_requires_registry_defined_combo():
    from audit_rules.technology.applicability import cms_applicability_decision
    assert cms_applicability_decision(
        _profile_with_wordpress(confidence="Medium", strong_count=2),
        signature_requirement="STRONG_2") == "wordpress_remote"
    assert cms_applicability_decision(
        _profile_with_wordpress(confidence="Medium", strong_count=1),
        signature_requirement="STRONG_2") == "generic"


def test_high_confidence_drives_applicability():
    from audit_rules.technology.applicability import cms_applicability_decision
    assert cms_applicability_decision(
        _profile_with_wordpress(confidence="High")) == "wordpress_remote"


def test_conflicting_cms_does_not_drive_applicability():
    from audit_rules.technology.applicability import cms_applicability_decision
    profile = _profile_with_wordpress(confidence="Medium", status="CONFLICTING",
                                      strong_count=2)
    assert cms_applicability_decision(profile) == "generic"


def test_generic_cms_profile_keeps_wp_rules_not_applicable():
    row = _coverage_row(36, _site(profile="generic"))
    assert row.execution_status.value == "NOT_APPLICABLE"


def test_runner_injects_technology_profile_and_wp_applicability():
    from audit_rules.runner import RuleRunner
    from audit_rules.registry import load_registry
    pages = [{
        "url": "https://example.com/", "status_code": 200,
        "title": "T", "word_count": 300,
        "generator": "WordPress 6.4",
        "links_detailed": [
            {"url": "https://example.com/wp-content/themes/x/style.css"}],
        "images": [], "json_ld": [], "hreflang": [],
        "scripts": [], "stylesheets": [], "analytics": {},
    }]
    runner = RuleRunner(load_registry(), providers={})
    _, coverage = runner.run(
        site_data={"robots_txt": {"found": True},
                   "sitemap": {"found": True, "url": "https://example.com/sitemap.xml"}},
        pages=pages, links=[], base_url="https://example.com/",
    )
    profile = runner.last_shared_data.get("technology_profile") or {}
    wp = [d for d in profile.get("detections", [])
          if d.get("technology_name") == "WordPress"]
    assert wp and wp[0]["confidence"] == "High"
    risks = runner.last_shared_data.get("technology_risks") or []
    assert any(risk.technology == "WordPress"
               and 36 in risk.mapped_audit_ids for risk in risks)
    row36 = next(r for r in coverage if r.audit_id == 36)
    assert row36.execution_status.value != "NOT_APPLICABLE"
