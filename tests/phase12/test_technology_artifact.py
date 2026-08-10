"""Task I 鈥?09_Technology_Profile.json machine artifact."""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _profile():
    from audit_rules.technology.models import (
        TechnologyDetection, TechnologyEvidence, build_profile,
    )
    server_evidence = TechnologyEvidence(
        signal_type="response_header", signal_value="server=nginx",
        source_url="https://example.com/", source_scope="single_page",
        strength="strong", provenance="local_crawl")
    cms_evidence = TechnologyEvidence(
        signal_type="meta_generator", signal_value="WordPress",
        source_url="https://example.com/", source_scope="single_page",
        strength="strong", provenance="local_crawl")
    detections = [
        TechnologyDetection(
            category="Server", technology_name="nginx",
            technology_type="server", detection_sources=[server_evidence],
            confidence_score=0.9, confidence="High", status="DETECTED"),
        TechnologyDetection(
            category="CMS", technology_name="WordPress",
            technology_type="CMS", detection_sources=[cms_evidence],
            confidence_score=0.9, confidence="High", status="DETECTED"),
    ]
    return build_profile(
        detections, detector_version="1.0.0",
        signature_registry_version="1.0.0",
        source_url="https://example.com/", git_head="b" * 40)


def _risk():
    from audit_rules.technology.risks import TechnologyRiskCorrelator
    risks = TechnologyRiskCorrelator().correlate(_profile())
    return next(r for r in risks if r.technology == "WordPress")


def test_technology_artifact_contains_detector_version():
    from audit_rules.technology.artifact import serialize_technology_artifact
    payload = serialize_technology_artifact(_profile())
    assert payload["detector_version"] == "1.0.0"


def test_technology_artifact_contains_registry_version():
    from audit_rules.technology.artifact import serialize_technology_artifact
    payload = serialize_technology_artifact(_profile())
    assert payload["signature_registry_version"] == "1.0.0"


def test_technology_profile_contains_no_raw_internal_objects():
    from audit_rules.technology.artifact import serialize_technology_artifact
    payload = serialize_technology_artifact(_profile(), risks=[_risk()])
    # Must be fully JSON-serializable with no dataclass or repr leakage.
    text = json.dumps(payload)
    assert "TechnologyEvidence" not in text
    assert "object at 0x" not in text
    assert all(isinstance(detection, dict)
               for detection in payload["detections"])
    assert payload["risk_correlations"][0]["technology"] == "WordPress"
    assert 36 in payload["risk_correlations"][0]["mapped_audit_ids"]


def test_technology_artifact_serializes_from_replay_offline(tmp_path):
    from audit_rules.replay import (
        build_replay_document, load_replay_artifact,
        reconstruct_technology_profile, write_replay_artifact,
    )
    from audit_rules.technology.artifact import serialize_technology_artifact
    document = build_replay_document(
        source_url="https://example.com/",
        git_head="b" * 40,
        generated_at="2026-08-09T06:00:00Z",
        crawl_metadata={
            "crawl_parameters": {}, "truncation_status": "NOT_TRUNCATED"},
        pages=[{
            "url": "https://example.com/", "status_code": 200,
            "allowlisted_headers": {"server": "nginx"},
        }],
        links=[],
        site_data={},
        sitemap_reconciliation={},
        crawl_completeness={"pages_crawled": 1, "audit_complete": True},
        provider_evidence={},
        technology_profile=_profile(),
    )
    target = tmp_path / "example.audit-replay-v1.json.gz"
    write_replay_artifact(document, target, expected_completed_pages=1)
    loaded = load_replay_artifact(target, expected_completed_pages=1)
    profile = reconstruct_technology_profile(loaded)
    payload = serialize_technology_artifact(profile)
    assert payload["schema_version"] == "technology-profile-v1"
    assert payload["detections"][0]["technology_name"] == "nginx"
    assert payload["detections"][0]["detection_sources"][0][
        "signal_value"] == "server=nginx"
