"""Task L 鈥?generic cross-site fixtures; no customer-domain coupling."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _page(url="https://client-a.example/", *, scripts=None, stylesheets=None,
          generator=None, links=None, headers=None):
    from audit_rules.context import PageContext
    return PageContext.from_export({
        "url": url, "status_code": 200,
        "scripts": scripts or [],
        "stylesheets": stylesheets or [],
        "generator": generator,
        "links_detailed": links or [],
        "images": [],
        "response_headers": headers or {},
        "robots": "",
        "json_ld": [],
        "analytics": {},
    })


def _detector(pages):
    from audit_rules.technology.detector import LocalTechnologyDetector
    from audit_rules.technology.signatures import load_default_registry
    detector = LocalTechnologyDetector(
        registry=load_default_registry(),
        source_url="https://client-a.example/",
        git_head="a" * 40,
    )
    return detector.detect(pages, site_ctx=None)


def _generic_wordpress_pages(base="https://client-a.example/"):
    return [
        _page(base, generator="WordPress 6.4",
              links=[{"url": f"{base}wp-content/themes/x/style.css"}],
              headers={"Server": "nginx"}),
    ]


def _generic_non_wordpress_pages(base="https://client-a.example/"):
    return [
        _page(base,
              scripts=[f"{base}assets/js/shopify.js"],
              links=[{"url": f"{base}cdn/shop/t/1/theme.css"}],
              headers={"Server": "cloudflare"}),
    ]


def _conflicting_pages():
    return [
        _page("https://client-a.example/", generator="WordPress 6.4",
              links=[{"url": "https://client-a.example/wp-content/a.js"}]),
        _page("https://client-a.example/es/", generator="Webflow"),
    ]


def _insufficient_evidence_pages():
    return [_page("https://client-a.example/", generator=None)]


def _baolai_like_pages(base="https://client-a.example/"):
    return [
        _page(base, generator="WordPress 6.4",
              links=[{"url": f"{base}wp-content/x.css"}],
              headers={"Server": "nginx", "CF-Ray": "abc123"}),
    ]


def _gelgoogsort_like_pages(base="https://client-b.example/"):
    return [
        _page(base,
              scripts=[f"{base}assets/js/jquery.min.js"],
              stylesheets=[f"{base}assets/css/main.css"],
              headers={"Server": "nginx", "X-Powered-By": "PHP/8.1"}),
    ]


def _technology_names(profile) -> set[str]:
    return {
        detection["technology_name"]
        for detection in profile.get("detections", [])
    }


def test_generic_wordpress_like_fixture_detected():
    profile = _detector(_generic_wordpress_pages())
    detections = {
        d["technology_name"]: d for d in profile["detections"]
    }
    assert "WordPress" in detections
    assert detections["WordPress"]["status"] == "DETECTED"
    assert detections["WordPress"]["confidence"] == "High"
    assert detections["WordPress"]["version"] == "6.4"


def test_generic_non_wordpress_fixture_not_reported_as_wordpress():
    profile = _detector(_generic_non_wordpress_pages())
    names = _technology_names(profile)
    assert "WordPress" not in names
    assert "WordPress" in profile.get("not_detected_technologies", [])


def test_conflicting_signals_fixture_flags_conflict():
    profile = _detector(_conflicting_pages())
    detections = {
        d["technology_name"]: d for d in profile["detections"]
    }
    assert "WordPress" in detections and "Webflow" in detections
    assert detections["WordPress"]["status"] == "CONFLICTING"
    assert detections["Webflow"]["status"] == "CONFLICTING"


def test_unknown_insufficient_evidence_fixture_returns_unknown():
    profile = _detector(_insufficient_evidence_pages())
    assert profile["detections"] == []
    # NOT_DETECTED never claims definite absence; it is listed as such.
    assert "WordPress" in profile.get("not_detected_technologies", [])


def test_baolai_specific_stack_not_reused():
    profile = _detector(_baolai_like_pages())
    names = _technology_names(profile)
    assert "WordPress" in names
    assert "nginx" in names
    # Identical signals on an unrelated domain yield the same technology set.
    other = _detector(_baolai_like_pages(
        base="https://unrelated-client.example/"))
    assert _technology_names(other) == names


def test_second_site_stack_not_reused():
    profile = _detector(_gelgoogsort_like_pages())
    names = _technology_names(profile)
    assert "jQuery" in names
    assert "nginx" in names
    assert "PHP" not in names  # PHP is not a registry technology; no guess.
    other = _detector(_gelgoogsort_like_pages(
        base="https://unrelated-client.example/"))
    assert _technology_names(other) == names
