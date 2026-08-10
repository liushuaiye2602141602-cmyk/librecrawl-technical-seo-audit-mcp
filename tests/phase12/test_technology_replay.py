"""Task H 鈥?technology evidence survives replay; offline reconstruction."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _profile_dict(detector_version="1.0.0", registry_version="1.0.0"):
    from audit_rules.technology.models import (
        TechnologyDetection, TechnologyEvidence, build_profile,
    )
    evidence = TechnologyEvidence(
        signal_type="response_header", signal_value="server=nginx",
        source_url="https://example.com/", source_scope="single_page",
        strength="strong", provenance="local_crawl")
    detection = TechnologyDetection(
        category="Server", technology_name="nginx",
        technology_type="server", detection_sources=[evidence],
        confidence_score=0.9, confidence="High", status="DETECTED")
    return build_profile(
        [detection], detector_version=detector_version,
        signature_registry_version=registry_version,
        source_url="https://example.com/", git_head="b" * 40)


def _document(technology_profile=None, pages=None):
    from audit_rules.replay import build_replay_document
    return build_replay_document(
        source_url="https://example.com/",
        git_head="b" * 40,
        generated_at="2026-08-09T06:00:00Z",
        crawl_metadata={
            "crawl_parameters": {}, "truncation_status": "NOT_TRUNCATED"},
        pages=pages or [{
            "url": "https://example.com/", "status_code": 200,
            "allowlisted_headers": {"server": "nginx"},
        }],
        links=[],
        site_data={},
        sitemap_reconciliation={},
        crawl_completeness={"pages_crawled": 1, "audit_complete": True},
        provider_evidence={},
        technology_profile=technology_profile,
    )


def test_technology_profile_available_from_replay(tmp_path):
    from audit_rules.replay import (
        load_replay_artifact, write_replay_artifact,
    )
    document = _document(_profile_dict())
    target = tmp_path / "example.audit-replay-v1.json.gz"
    write_replay_artifact(document, target, expected_completed_pages=1)
    loaded = load_replay_artifact(target, expected_completed_pages=1)
    profile = loaded["technology_profile"]
    assert profile["schema_version"] == "technology-profile-v1"
    assert profile["detections"][0]["technology_name"] == "nginx"
    assert profile["detections"][0]["detection_sources"][0][
        "signal_value"] == "server=nginx"


def test_replay_reconstruction_uses_snapshot_not_live_api():
    from audit_rules.replay import reconstruct_technology_profile
    document = _document(_profile_dict())
    profile = reconstruct_technology_profile(document)
    assert profile["detections"][0]["technology_name"] == "nginx"
    assert (
        profile["detections"][0]["detection_sources"][0]["signal_value"]
        == "server=nginx"
    )
    # No external provider was touched: replay evidence section stays empty.
    assert document["provider_evidence"] == {}


def test_technology_replay_parity_after_signature_update_is_versioned():
    from audit_rules.replay import reconstruct_technology_profile
    document = _document(_profile_dict(registry_version="1.0.0"))
    profile = reconstruct_technology_profile(
        document, current_signature_registry_version="2.0.0")
    # Snapshot is preserved and versioned; no silent re-detection.
    assert profile["signature_registry_version"] == "1.0.0"
    assert profile["detections"][0]["technology_name"] == "nginx"
    assert any(
        "signature_registry_version" in limitation
        for limitation in profile.get("limitations", [])
    )


def test_sensitive_header_values_absent_from_replay(tmp_path):
    from dataclasses import replace

    from audit_rules.replay import (
        load_replay_artifact, write_replay_artifact,
    )
    profile = _profile_dict()
    evidence = replace(
        profile["detections"][0]["detection_sources"][0],
        signal_value=(
        "server=nginx; Authorization: Bearer SECRET-TOKEN-12345"
        ),
    )
    profile["detections"][0]["detection_sources"] = [evidence]
    document = _document(profile)
    target = tmp_path / "safe.audit-replay-v1.json.gz"
    write_replay_artifact(document, target, expected_completed_pages=1)
    loaded = load_replay_artifact(target, expected_completed_pages=1)
    payload = str(loaded)
    assert "secret" not in payload.lower()
    assert "bearer" not in payload.lower()
