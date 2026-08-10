"""FINAL TECHNOLOGY CLAIM PRECISION regressions.

Technology signal observed != technology confirmed:
- Low confidence never produces DETECTED (stays an UNKNOWN observation).
- Generic, non-vendor-specific Medium evidence (e.g. WooCommerce /product/)
  never produces DETECTED.
- Vendor-specific evidence can confirm the technology.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _page(url="https://example.com/", *, scripts=None, stylesheets=None,
          generator=None, links=None, images=None, headers=None,
          robots=""):
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
        "json_ld": [],
        "analytics": {},
    })


def _detector(pages):
    from audit_rules.technology.detector import LocalTechnologyDetector
    from audit_rules.technology.signatures import load_default_registry
    detector = LocalTechnologyDetector(
        registry=load_default_registry(),
        source_url="https://example.com/",
        git_head="a" * 40,
    )
    return detector.detect(pages, site_ctx=None)


def _by_name(profile):
    return {d["technology_name"]: d for d in profile["detections"]}


def test_weak_yoast_robots_meta_is_not_confirmed_detection():
    pages = [_page("https://example.com/",
                   robots="index, follow, max-image-preview:large")]
    profile = _detector(pages)
    yoast = _by_name(profile).get("Yoast SEO")
    assert yoast is not None  # observation preserved
    assert yoast["status"] == "UNKNOWN"
    assert yoast["confidence"] == "Low"
    assert yoast["detection_sources"]  # evidence kept


def test_low_confidence_detection_is_not_reported_as_confirmed():
    from audit_rules.technology.models import (
        TechnologyDetection, TechnologyEvidence,
    )
    evidence = TechnologyEvidence(
        signal_type="robots_meta",
        signal_value="max-image-preview:large",
        source_url="https://example.com/", source_scope="single_page",
        strength="weak", pattern=r"max-image-preview:large")
    detection = TechnologyDetection(
        category="SEO Technology", technology_name="Yoast SEO",
        technology_type="SEO Plugin", detection_sources=[evidence])
    assert detection.confidence == "Low"
    assert detection.status == "UNKNOWN"


def test_generic_product_path_is_not_woocommerce_confirmation():
    pages = [
        _page("https://example.com/product/apple-sorter/"),
        _page("https://example.com/product/tomato-grader/"),
    ]
    profile = _detector(pages)
    woo = _by_name(profile).get("WooCommerce")
    assert woo is not None
    assert woo["status"] == "UNKNOWN"
    assert woo["confidence"] == "Medium"
    assert woo["detection_sources"]


def test_woocommerce_specific_asset_can_confirm_woocommerce():
    pages = [
        _page("https://example.com/",
              images=[{"src":
                       "https://example.com/wp-content/plugins/"
                       "woocommerce/assets/css/woocommerce.css"}]),
    ]
    profile = _detector(pages)
    woo = _by_name(profile).get("WooCommerce")
    assert woo is not None
    assert woo["status"] == "DETECTED"
    assert woo["confidence"] == "High"


def test_custom_post_type_product_path_does_not_false_positive_woocommerce():
    pages = [
        _page("https://example.com/product/foo/",
              generator="WordPress 6.4",
              images=[{"src": "https://example.com/wp-content/uploads/a.png"}]),
    ]
    profile = _detector(pages)
    by_name = _by_name(profile)
    assert by_name["WordPress"]["status"] == "DETECTED"
    woo = by_name.get("WooCommerce")
    # A /product/ path on a plain WordPress install is a custom post type,
    # not confirmed WooCommerce.
    assert woo is None or woo["status"] == "UNKNOWN"
