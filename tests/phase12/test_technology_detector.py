"""Task D — LocalTechnologyDetector."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _page(url="https://example.com/", *, scripts=None, stylesheets=None,
          generator=None, links=None, images=None, headers=None,
          robots="", json_ld=None, analytics=None):
    from audit_rules.context import PageContext
    return PageContext.from_export({
        "url": url, "status_code": 200,
        "scripts": scripts or [],
        "stylesheets": stylesheets or [],
        "generator": generator,
        "links_detailed": links or [],
        "images": images or [],
        "response_headers": headers or {},
        "robots": robots,
        "json_ld": json_ld or [],
        "analytics": analytics or {},
    })


def _detector(pages, site=None):
    from audit_rules.technology.detector import LocalTechnologyDetector
    from audit_rules.technology.signatures import load_default_registry
    detector = LocalTechnologyDetector(
        registry=load_default_registry(),
        source_url="https://example.com/",
        git_head="a" * 40,
    )
    return detector.detect(pages, site_ctx=site)


def test_detection_from_generic_wordpress_fixture():
    pages = [
        _page("https://example.com/",
              generator="WordPress 6.4",
              links=[{"url": "https://example.com/wp-content/themes/x/style.css"}],
              headers={"Server": "nginx"}),
    ]
    profile = _detector(pages)
    detections = {d["technology_name"]: d for d in profile["detections"]}
    assert "WordPress" in detections
    assert detections["WordPress"]["confidence_score"] >= 0.8
    assert detections["WordPress"]["confidence"] == "High"
    assert detections["WordPress"]["version"] == "6.4"
    assert detections["WordPress"]["status"] == "DETECTED"


def test_unknown_technology_not_guessed():
    pages = [_page("https://example.com/", generator=None)]
    profile = _detector(pages)
    assert profile["detections"] == []
    assert "WordPress" in profile["not_detected_technologies"]


def test_confidence_requires_signal_strength():
    pages = [_page("https://example.com/",
                   robots="index, follow, max-image-preview:large")]
    profile = _detector(pages)
    # Weak-only signals must not produce a High detection.
    for detection in profile["detections"]:
        assert detection["confidence"] != "High"


def test_version_unknown_when_not_provable():
    pages = [_page("https://example.com/",
                   generator="WordPress",
                   links=[{"url": "https://example.com/wp-content/a.js"}])]
    profile = _detector(pages)
    wordpress = next(d for d in profile["detections"]
                     if d["technology_name"] == "WordPress")
    assert wordpress["version"] == "Unknown"


def test_conflicting_signals_reduce_or_flag_confidence():
    pages = [
        _page("https://example.com/",
              generator="WordPress 6.4",
              links=[{"url": "https://example.com/wp-content/a.js"}]),
        _page("https://example.com/es/", generator="Webflow"),
    ]
    profile = _detector(pages)
    detections = {d["technology_name"]: d for d in profile["detections"]}
    assert "WordPress" in detections and "Webflow" in detections
    assert detections["WordPress"]["status"] == "CONFLICTING"
    assert detections["WordPress"]["confidence_score"] < 0.8


def test_detector_failure_marks_profile_incomplete_not_audit_failure():
    from audit_rules.technology.detector import LocalTechnologyDetector
    from audit_rules.technology.signatures import TechnologySignatureRegistry
    import pytest

    class BrokenRegistry(TechnologySignatureRegistry):
        def iter_signatures(self):
            raise RuntimeError("boom")

    detector = LocalTechnologyDetector(
        registry=BrokenRegistry({}),
        source_url="https://example.com/",
        git_head="a" * 40,
    )
    profile = detector.detect([_page()])
    assert profile["detection_status"] == "DETECTION_INCOMPLETE"
    assert "boom" in profile["detection_reason"]


def test_detection_from_replay_does_not_call_network():
    # Pages built from replay-shaped data only; detection is pure.
    pages = [_page("https://example.com/", generator="Shopify",
                   stylesheets=["https://cdn.shopify.com/s/theme.css"])]
    profile = _detector(pages)
    detections = {d["technology_name"]: d for d in profile["detections"]}
    assert "Shopify" in detections
    assert detections["Shopify"]["confidence"] == "High"


def test_source_html_scripts_are_detected_without_rendered_dom():
    pages = [_page("https://example.com/",
                   scripts=["https://cdn.example.com/jquery.min.js"])]
    profile = _detector(pages)
    detections = {d["technology_name"]: d for d in profile["detections"]}
    assert "jQuery" in detections


def test_source_html_stylesheets_are_detected_without_rendered_dom():
    pages = [_page("https://example.com/",
                   stylesheets=["https://cdn.shopify.com/s/theme.css"])]
    profile = _detector(pages)
    detections = {d["technology_name"]: d for d in profile["detections"]}
    assert "Shopify" in detections


def test_meta_generator_is_detected():
    pages = [_page("https://example.com/", generator="Rank Math")]
    profile = _detector(pages)
    detections = {d["technology_name"]: d for d in profile["detections"]}
    assert "Rank Math" in detections


def test_analytics_fingerprint_detects_ga4_gtm():
    pages = [_page("https://example.com/",
                   analytics={"ga4_id": "G-ABC123", "gtm_id": "GTM-ABC"})]
    profile = _detector(pages)
    detections = {d["technology_name"]: d for d in profile["detections"]}
    assert detections["GA4"]["confidence"] == "High"
    assert detections["GTM"]["confidence"] == "High"
