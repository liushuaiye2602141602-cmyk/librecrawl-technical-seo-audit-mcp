"""Task B — technology data contracts."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _evidence(signal_type="meta_generator", value="WordPress 6.4",
              strength="strong", url="https://example.com/"):
    from audit_rules.technology.models import TechnologyEvidence
    return TechnologyEvidence(
        signal_type=signal_type, signal_value=value,
        source_url=url, source_scope="single_page",
        strength=strength, provenance="local_crawl")


def test_technology_profile_always_present():
    from audit_rules.technology.models import build_profile
    profile = build_profile(
        [], detector_version="1.0.0", signature_registry_version="1.0.0",
        source_url="https://example.com/", git_head="a" * 40)
    assert profile["schema_version"] == "technology-profile-v1"
    assert profile["detector_version"] == "1.0.0"
    assert profile["signature_registry_version"] == "1.0.0"
    assert profile["detections"] == []
    assert profile["detection_status"] == "COMPLETE"


def test_technology_detection_requires_evidence():
    from audit_rules.technology.models import TechnologyDetection
    with pytest.raises(ValueError):
        TechnologyDetection(
            category="CMS", technology_name="WordPress",
            technology_type="CMS",
            detection_sources=[])


def test_technology_profile_does_not_create_rule_81():
    from audit_rules.registry import load_registry
    registry = load_registry()
    assert len(registry) == 80
    assert [r.audit_id for r in registry] == list(range(1, 81))


def test_not_detected_is_not_reported_as_definitely_absent():
    from audit_rules.technology.models import status_wording
    text = status_wording("NOT_DETECTED")
    assert "not detected" in text.lower()
    assert "definitely" not in text.lower()
    assert "absolutely" not in text.lower()


def test_unknown_technology_not_guessed():
    from audit_rules.technology.models import status_wording
    text = status_wording("UNKNOWN")
    assert "unknown" in text.lower()
    assert "is" not in text.lower() or "cannot" in text.lower()


def test_technology_artifact_contains_detector_and_registry_version():
    from audit_rules.technology.models import build_profile
    profile = build_profile(
        [], detector_version="2.3.4", signature_registry_version="1.2.0",
        source_url="https://example.com/", git_head="a" * 40)
    assert profile["detector_version"] == "2.3.4"
    assert profile["signature_registry_version"] == "1.2.0"


def test_same_type_different_values_are_not_automatic_conflict():
    from audit_rules.technology.models import aggregate_confidence
    a = _evidence(value="WordPress")
    b = _evidence(value="Webflow")
    # Different signal values under one signal type are corroborating
    # evidence, never a same-detection conflict. CONFLICTING status is
    # decided by the detector from mutually-exclusive technology judgments.
    score, conflicting = aggregate_confidence([a, b])
    assert conflicting is False
    score2, conflict2 = aggregate_confidence([a, a])
    assert conflict2 is False
    assert score2 >= 0.8


def test_confidence_requires_signal_strength():
    from audit_rules.technology.models import aggregate_confidence, confidence_label
    weak = _evidence(signal_type="robots_meta", value="max-image-preview",
                     strength="weak")
    score, _ = aggregate_confidence([weak])
    assert score < 0.6
    assert confidence_label(score) == "Low"


def test_evidence_is_structured():
    evidence = _evidence()
    assert evidence.signal_type == "meta_generator"
    assert evidence.signal_value == "WordPress 6.4"
    assert evidence.source_url == "https://example.com/"
    assert evidence.source_scope == "single_page"
    assert evidence.strength == "strong"
    assert evidence.provenance == "local_crawl"
