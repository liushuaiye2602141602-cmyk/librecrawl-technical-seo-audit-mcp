"""FINAL TECHNOLOGY SEMANTICS regressions.

Locks the corrected conflict/confidence contract:
- Multiple URLs/pages matching one signature family corroborate; they never
  produce CONFLICTING and never inflate confidence to the two-family level.
- CONFLICTING comes only from genuinely mutually-exclusive technology
  judgments (credible competing CMS candidates or declared negative signals).
- Weak competing candidates never poison strong detections.
- The broad Webflow weak signature is gone.
"""

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


def test_multiple_wordpress_asset_paths_are_not_conflicting():
    pages = [
        _page("https://example.com/news/a/",
              images=[{"src": f"https://example.com/wp-content/uploads/x{i}.png"}
                      for i in range(8)]),
    ]
    profile = _detector(pages)
    wp = _by_name(profile).get("WordPress")
    assert wp is not None
    assert wp["status"] == "DETECTED"
    assert wp["confidence"] == "High"
    assert wp["confidence_score"] < 0.92


def test_multiple_pages_same_signature_are_corroborating():
    pages = [
        _page(f"https://example.com/news/{i}/",
              images=[{"src": "https://example.com/wp-content/uploads/a.png"}])
        for i in range(5)
    ]
    profile = _detector(pages)
    wp = _by_name(profile).get("WordPress")
    assert wp is not None
    assert wp["status"] == "DETECTED"
    # 5 pages corroborate one strong family: bounded boost, never 0.92.
    assert wp["confidence_score"] == 0.82


def test_different_urls_same_signal_type_are_not_conflict():
    pages = [
        _page("https://example.com/product/apple-sorter/"),
        _page("https://example.com/product/tomato-grader/"),
    ]
    profile = _detector(pages)
    woo = _by_name(profile).get("WooCommerce")
    assert woo is not None
    # Generic /product/ URLs are not a vendor-specific confirmation: the
    # observation is preserved as UNKNOWN/Medium, not DETECTED.
    assert woo["status"] == "UNKNOWN"
    assert woo["confidence"] == "Medium"
    assert woo["conflicting_signals"] == []


def test_weak_competing_cms_does_not_poison_strong_cms_detection():
    pages = [
        _page("https://example.com/", generator="WordPress 6.4",
              images=[{"src": "https://example.com/wp-content/uploads/a.png"}]),
        _page("https://example.com/products/apple-sorter/"),
    ]
    profile = _detector(pages)
    by_name = _by_name(profile)
    wp = by_name.get("WordPress")
    shopify = by_name.get("Shopify")
    assert wp is not None and wp["status"] == "DETECTED"
    assert wp["confidence"] == "High"
    # The weak Shopify URL-pattern signal stays a Low observation; it must
    # not downgrade the strong WordPress detection to CONFLICTING.
    assert shopify is None or shopify["confidence"] == "Low"
    assert shopify is None or shopify["status"] != "CONFLICTING"


def test_strong_mutually_exclusive_cms_signals_can_conflict():
    pages = [
        _page("https://example.com/", generator="WordPress 6.4",
              images=[{"src": "https://example.com/wp-content/uploads/a.png"}]),
        _page("https://example.com/shop/", generator="Shopify"),
    ]
    profile = _detector(pages)
    by_name = _by_name(profile)
    wp = by_name.get("WordPress")
    shopify = by_name.get("Shopify")
    assert wp is not None and shopify is not None
    assert wp["status"] == "CONFLICTING"
    assert shopify["status"] == "CONFLICTING"
    assert wp["confidence_score"] <= 0.45
    assert shopify["confidence_score"] <= 0.45


def test_generic_assets_js_is_not_webflow():
    pages = [_page("https://example.com/",
                   scripts=["https://example.com/assets/app.js"])]
    profile = _detector(pages)
    assert "Webflow" not in _by_name(profile)


def test_two_independent_strong_families_reach_high():
    pages = [
        _page("https://example.com/",
              images=[
                  {"src": "https://example.com/wp-content/uploads/a.png"},
                  {"src": "https://example.com/wp-includes/js/x.js"},
              ]),
    ]
    profile = _detector(pages)
    wp = _by_name(profile).get("WordPress")
    assert wp is not None and wp["confidence_score"] == 0.92


def test_strong_negative_signal_conflicts_credible_positive():
    pages = [
        _page("https://example.com/", generator="WordPress 6.4",
              images=[{"src": "https://example.com/wp-content/uploads/a.png"}]),
        _page("https://example.com/es/", generator="Webflow"),
    ]
    profile = _detector(pages)
    wp = _by_name(profile).get("WordPress")
    assert wp is not None
    assert wp["status"] == "CONFLICTING"
    assert any("meta_generator" in item
               for item in wp["conflicting_signals"])
