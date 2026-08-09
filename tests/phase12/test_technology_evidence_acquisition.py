"""Task A — safe crawl evidence acquisition for Technology Intelligence."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _page_dict(**overrides):
    base = {"url": "https://example.com/", "status_code": 200}
    base.update(overrides)
    return base


def test_safe_headers_only_are_persisted():
    from audit_rules.context import PageContext
    raw = {
        "Server": "nginx",
        "X-Powered-By": "PHP/8.1",
        "CF-Ray": "abc123",
        "Cache-Control": "public, max-age=300",
        "X-Custom-Secret": "leak",
        "X-Robots-Tag": "index",
    }
    ctx = PageContext.from_export(_page_dict(response_headers=raw))
    headers = ctx.allowlisted_headers or {}
    assert headers.get("server") == "nginx"
    assert headers.get("x-powered-by") == "PHP/8.1"
    assert headers.get("cf-ray") == "abc123"
    assert headers.get("cache-control") == "public, max-age=300"
    assert headers.get("x-robots-tag") == "index"
    assert "x-custom-secret" not in headers


def test_sensitive_headers_are_never_persisted():
    from audit_rules.context import PageContext
    raw = {
        "Authorization": "Bearer abc.def.ghi",
        "Cookie": "session=abc123",
        "Set-Cookie": "PHPSESSID=abc123; path=/",
        "X-API-Key": "secret-key",
        "Server": "nginx",
    }
    ctx = PageContext.from_export(_page_dict(response_headers=raw))
    headers = ctx.allowlisted_headers or {}
    for name in ("authorization", "cookie", "set-cookie", "x-api-key"):
        assert name not in headers
    assert headers.get("server") == "nginx"


def test_set_cookie_values_are_not_persisted():
    from audit_rules.context import PageContext
    ctx = PageContext.from_export(_page_dict(
        response_headers={"Set-Cookie": "PHPSESSID=abc123; path=/",
                          "CF-Cache-Status": "HIT"}))
    headers = ctx.allowlisted_headers or {}
    assert "set-cookie" not in headers
    assert headers.get("cf-cache-status") == "HIT"


def test_cookie_values_not_persisted():
    from audit_rules.context import PageContext
    from audit_rules.technology.detector import LocalTechnologyDetector
    ctx = PageContext.from_export(_page_dict(
        response_headers={
            "Cookie": "session=abc123; theme=dark",
            "Set-Cookie": "PHPSESSID=abc123; path=/",
            "Server": "nginx",
        }))
    headers = ctx.allowlisted_headers or {}
    assert "cookie" not in headers
    assert "set-cookie" not in headers
    # The detector records cookie names only, never values.
    corpus = LocalTechnologyDetector._build_corpus(ctx)
    assert corpus["cookie_name"] == []
    joined = " ".join(
        str(value) for values in corpus.values() for value in values)
    assert "abc123" not in joined
    assert "session=" not in joined


def test_source_html_scripts_are_detected_without_rendered_dom():
    from audit_rules.context import PageContext
    ctx = PageContext.from_export(_page_dict(
        scripts=["https://cdn.example.com/jquery.min.js"]))
    assert "https://cdn.example.com/jquery.min.js" in (ctx.scripts or [])


def test_source_html_stylesheets_are_detected_without_rendered_dom():
    from audit_rules.context import PageContext
    ctx = PageContext.from_export(_page_dict(
        stylesheets=["https://cdn.example.com/style.css"]))
    assert "https://cdn.example.com/style.css" in (ctx.stylesheets or [])


def test_meta_generator_is_detected():
    from audit_rules.context import PageContext
    ctx = PageContext.from_export(_page_dict(generator="WordPress 6.4"))
    assert ctx.meta_generator == "WordPress 6.4"


def test_export_fields_request_technology_signals():
    import server
    for field in ("response_headers", "scripts", "stylesheets", "generator"):
        assert field in server.EXPORT_FIELDS


def test_replay_preserves_allowlisted_technology_fields():
    from audit_rules.replay import REPLAY_PAGE_FIELDS, build_replay_document
    for field in ("allowlisted_headers", "scripts", "stylesheets", "generator"):
        assert field in REPLAY_PAGE_FIELDS
    document = build_replay_document(
        source_url="https://example.com/",
        git_head="a" * 40,
        generated_at="2026-08-10T00:00:00Z",
        crawl_metadata={"crawl_parameters": {},
                        "truncation_status": "NOT_TRUNCATED"},
        pages=[_page_dict(
            generator="WordPress 6.4",
            scripts=["https://cdn.example.com/jquery.min.js"],
            stylesheets=["https://cdn.example.com/style.css"],
            allowlisted_headers={"server": "nginx"},
        )],
        links=[],
        site_data={"robots_txt": {"found": True}},
        sitemap_reconciliation={},
        crawl_completeness={"pages_crawled": 1, "audit_complete": True},
    )
    page = document["pages"][0]
    assert page["generator"] == "WordPress 6.4"
    assert page["scripts"] == ["https://cdn.example.com/jquery.min.js"]
    assert page["stylesheets"] == ["https://cdn.example.com/style.css"]
    assert page["allowlisted_headers"] == {"server": "nginx"}
