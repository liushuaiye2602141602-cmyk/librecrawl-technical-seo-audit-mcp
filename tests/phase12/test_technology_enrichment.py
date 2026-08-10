"""Task G 鈥?Optional external enrichment interface (contract only)."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _profile():
    from audit_rules.technology.models import (
        TechnologyDetection, TechnologyEvidence, build_profile,
    )
    evidence = TechnologyEvidence(
        signal_type="meta_generator", signal_value="WordPress",
        source_url="https://example.com/", source_scope="single_page",
        strength="strong", provenance="local_crawl")
    detection = TechnologyDetection(
        category="CMS", technology_name="WordPress",
        technology_type="CMS", detection_sources=[evidence],
        confidence_score=0.9, confidence="High", status="DETECTED")
    return build_profile(
        [detection], detector_version="1.0.0",
        signature_registry_version="1.0.0",
        source_url="https://example.com/", git_head="abc123")


class _FailingProvider:
    name = "exploding"

    def enrich(self, profile):
        raise RuntimeError("quota exceeded")


class _FakeProvider:
    name = "fake_wappalyzer"

    def enrich(self, profile):
        from audit_rules.technology.enrichment import EnrichmentFact
        return [
            EnrichmentFact(
                technology_name="WordPress", category="CMS",
                version="7.0", signal_value="WordPress",
                source_provenance="external_api"),
        ]


def test_external_enrichment_optional():
    from audit_rules.technology.enrichment import run_enrichment
    profile = _profile()
    status = run_enrichment(profile, providers=[])
    assert status["status"] == "unavailable"
    assert profile["external_enrichment"]["status"] == "unavailable"
    # Local detections are untouched and audit-relevant data survives.
    assert len(profile["detections"]) == 1
    assert profile["detections"][0]["technology_name"] == "WordPress"


def test_external_failure_does_not_block_audit():
    from audit_rules.technology.enrichment import run_enrichment
    profile = _profile()
    status = run_enrichment(profile, providers=[_FailingProvider()])
    assert status["status"] == "unavailable"
    assert "error" in status
    assert profile["detections"][0]["technology_name"] == "WordPress"


def test_external_results_never_silently_override_local():
    from audit_rules.technology.enrichment import run_enrichment
    profile = _profile()
    status = run_enrichment(profile, providers=[_FakeProvider()])
    assert status["status"] == "ok"
    facts = status["facts"]
    assert facts and facts[0]["technology_name"] == "WordPress"
    assert facts[0]["source_provenance"] == "external_api"
    # Local evidence stays primary: provenance unchanged, version untouched.
    assert profile["detections"][0]["version"] == "Unknown"
    assert (
        profile["detections"][0]["detection_sources"][0].provenance
        == "local_crawl"
    )


def test_enrichment_unavailable_recorded_in_profile():
    from audit_rules.technology.enrichment import (
        NoOpTechnologyEnrichmentProvider, run_enrichment,
    )
    profile = _profile()
    status = run_enrichment(
        profile, providers=[NoOpTechnologyEnrichmentProvider()])
    assert status["status"] == "unavailable"
    assert profile["external_enrichment"]["provider"] == "noop"
    assert profile["external_enrichment"]["facts"] == []
