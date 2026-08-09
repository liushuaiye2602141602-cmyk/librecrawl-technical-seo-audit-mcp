"""Task 3: PageContext + SiteContext tests.

Tests cover:
  - Lightweight field population from export data
  - Heavy field lazy loading / release lifecycle
  - from_export() factory with realistic LibreCrawl data
  - Memory efficiency (<2KB per context for lightweight)
  - SiteContext.from_site_check() parsing
  - Edge cases: empty data, missing fields, None values
"""

import sys
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def sample_export_page():
    """Realistic LibreCrawl export page dict (30+ fields)."""
    return {
        "url": "https://example.com/page1",
        "status_code": 200,
        "title": "Example Page Title",
        "meta_description": "A sample page for testing",
        "h1": "Welcome to Example",
        "canonical_url": "https://example.com/page1",
        "robots": "index, follow",
        "word_count": 450,
        "response_time_ms": 320,
        "depth": 2,
        "lang": "en",
        "viewport": "width=device-width, initial-scale=1.0",
        "charset": "utf-8",
        "images": [
            {"src": "/img/logo.png", "alt": "Logo", "broken": False},
            {"src": "/img/banner.jpg", "alt": "", "broken": True, "status": 404},
            {"src": "/img/hero.png", "alt": "Hero Image", "broken": False},
        ],
        "hreflang": [
            {"lang": "en", "url": "https://example.com/page1"},
            {"lang": "zh", "url": "https://example.com/zh/page1"},
        ],
        "json_ld": [
            {"@type": "Organization", "name": "Example Corp"},
            {"@type": "BreadcrumbList", "itemListElement": []},
        ],
        "links_detailed": [
            {"url": "https://example.com/about", "anchor": "About", "is_internal": True, "rel": ""},
            {"url": "https://example.com/contact", "anchor": "Contact", "is_internal": True, "rel": ""},
            {"url": "https://external.com", "anchor": "Partner", "is_internal": False, "rel": "nofollow"},
        ],
        "linked_from": ["https://example.com/home", "https://example.com/category"],
        "body_html": "<html><body><h1>Test</h1><p>Content here</p></body></html>",
        "body_text": "Test Content here",
        "response_headers": {"content-type": "text/html", "x-cache": "HIT"},
    }


@pytest.fixture
def sample_site_data():
    """Realistic _site_check() result."""
    return {
        "robots_txt": {
            "found": True,
            "disallow_count": 3,
            "sitemap_url": "https://example.com/sitemap.xml",
        },
        "sitemap": {
            "found": True,
            "url": "https://example.com/sitemap.xml",
            "url_count": 45,
        },
        "https_redirect": {"redirects": True},
        "www_redirect": {"redirects": False},
    }


@pytest.fixture
def sample_completeness():
    """Crawl completeness dict."""
    return {
        "pages_crawled": 45,
        "sitemap_total": 50,
        "sitemap_only_count": 5,
        "sitemap_coverage_pct": 90.0,
        "audit_complete": True,
        "incomplete_reasons": "",
    }


# ============================================================
# Test: PageContext — lightweight fields
# ============================================================

class TestPageContextLightweight:
    """Verify lightweight fields are eagerly populated from export data."""

    def test_from_export_populates_url_and_status(self, sample_export_page):
        from audit_rules.context import PageContext
        ctx = PageContext.from_export(sample_export_page)
        assert ctx.url == "https://example.com/page1"
        assert ctx.status_code == 200

    def test_from_export_populates_seo_meta(self, sample_export_page):
        from audit_rules.context import PageContext
        ctx = PageContext.from_export(sample_export_page)
        assert ctx.title == "Example Page Title"
        assert ctx.meta_description == "A sample page for testing"
        assert ctx.h1 == "Welcome to Example"
        assert ctx.canonical_url == "https://example.com/page1"
        assert ctx.robots == "index, follow"

    def test_from_export_populates_page_stats(self, sample_export_page):
        from audit_rules.context import PageContext
        ctx = PageContext.from_export(sample_export_page)
        assert ctx.word_count == 450
        assert ctx.response_time_ms == 320
        assert ctx.depth == 2

    def test_from_export_populates_technical_fields(self, sample_export_page):
        from audit_rules.context import PageContext
        ctx = PageContext.from_export(sample_export_page)
        assert ctx.lang == "en"
        assert ctx.viewport == "width=device-width, initial-scale=1.0"
        assert ctx.charset == "utf-8"

    def test_from_export_computes_image_summary(self, sample_export_page):
        from audit_rules.context import PageContext
        ctx = PageContext.from_export(sample_export_page)
        assert ctx.image_summary is not None
        assert ctx.image_summary["count"] == 3
        assert ctx.image_summary["broken"] == 1
        assert ctx.image_summary["missing_alt"] == 1  # banner.jpg has empty alt

    def test_from_export_no_images_produces_zero_summary(self):
        from audit_rules.context import PageContext
        page = {"url": "https://example.com", "images": []}
        ctx = PageContext.from_export(page)
        assert ctx.image_summary == {"count": 0, "broken": 0, "missing_alt": 0}

    def test_from_export_no_images_key_produces_zero_summary(self):
        from audit_rules.context import PageContext
        page = {"url": "https://example.com"}  # No "images" key
        ctx = PageContext.from_export(page)
        assert ctx.image_summary == {"count": 0, "broken": 0, "missing_alt": 0}

    def test_from_export_computes_hreflang_summary(self, sample_export_page):
        from audit_rules.context import PageContext
        ctx = PageContext.from_export(sample_export_page)
        assert ctx.hreflang_summary is not None
        assert len(ctx.hreflang_summary) == 2
        assert ctx.hreflang_summary[0]["lang"] == "en"
        assert ctx.hreflang_summary[1]["lang"] == "zh"

    def test_from_export_extracts_json_ld_types(self, sample_export_page):
        from audit_rules.context import PageContext
        ctx = PageContext.from_export(sample_export_page)
        assert ctx.json_ld_types == ["Organization", "BreadcrumbList"]

    def test_from_export_json_ld_string_handles_gracefully(self):
        from audit_rules.context import PageContext
        page = {"url": "https://example.com", "json_ld": "malformed"}
        ctx = PageContext.from_export(page)
        assert ctx.json_ld_types == ["parse_error"]

    def test_from_export_json_ld_none(self):
        from audit_rules.context import PageContext
        page = {"url": "https://example.com"}
        ctx = PageContext.from_export(page)
        assert ctx.json_ld_types == []

    def test_from_export_computes_link_counts(self, sample_export_page):
        from audit_rules.context import PageContext
        ctx = PageContext.from_export(sample_export_page)
        assert ctx.internal_links_count == 2
        assert ctx.external_links_count == 1
        assert ctx.linked_from_count == 2  # linked_from list

    def test_from_export_uses_numeric_link_counts_when_details_are_unavailable(self):
        """Production LibreCrawl exports counts without links_detailed."""
        from audit_rules.context import PageContext

        ctx = PageContext.from_export({
            "url": "https://example.com/",
            "status_code": 200,
            "internal_links": 104,
            "external_links": 8,
            "linked_from": ["https://example.com/about"],
        })

        assert ctx.internal_links_count == 104
        assert ctx.external_links_count == 8
        assert ctx.linked_from_count == 1

    def test_from_export_defaults_missing_fields(self):
        from audit_rules.context import PageContext
        page = {"url": "https://example.com/minimal"}
        ctx = PageContext.from_export(page)
        assert ctx.url == "https://example.com/minimal"
        assert ctx.status_code == 0
        assert ctx.title is None
        assert ctx.word_count == 0
        assert ctx.depth == 0
        assert ctx.lang is None

    def test_lightweight_fields_under_2kb(self, sample_export_page):
        """Requirement 6: lightweight fields ~2KB per page."""
        import sys
        from audit_rules.context import PageContext
        ctx = PageContext.from_export(sample_export_page)
        # Sum size of all non-heavy, non-private fields
        light_fields = {
            "url": ctx.url,
            "status_code": ctx.status_code,
            "title": ctx.title,
            "meta_description": ctx.meta_description,
            "h1": ctx.h1,
            "canonical_url": ctx.canonical_url,
            "robots": ctx.robots,
            "word_count": ctx.word_count,
            "response_time_ms": ctx.response_time_ms,
            "depth": ctx.depth,
            "lang": ctx.lang,
            "viewport": ctx.viewport,
            "charset": ctx.charset,
            "image_summary": ctx.image_summary,
            "hreflang_summary": ctx.hreflang_summary,
            "json_ld_types": ctx.json_ld_types,
            "links_detailed": ctx.links_detailed,
            "linked_from_count": ctx.linked_from_count,
            "internal_links_count": ctx.internal_links_count,
            "external_links_count": ctx.external_links_count,
        }
        total = sys.getsizeof(ctx.url) + sum(
            sys.getsizeof(k) + sys.getsizeof(v)
            for k, v in light_fields.items()
        )
        # Should be well under 3KB — typically 1-2KB for a normal page
        assert total < 3072, f"Lightweight fields total {total} bytes, expected <3072"


# ============================================================
# Test: PageContext — heavy fields (lazy load / release)
# ============================================================

class TestPageContextHeavyFields:
    """Verify heavy field lifecycle: lazy load, release, re-access."""

    def test_body_html_lazy_loaded(self, sample_export_page):
        from audit_rules.context import PageContext
        ctx = PageContext.from_export(sample_export_page)
        # Heavy not loaded yet
        assert ctx._html_loaded is False
        assert ctx._body_html is None
        # Access triggers lazy load
        html = ctx.body_html
        assert html == "<html><body><h1>Test</h1><p>Content here</p></body></html>"
        assert ctx._html_loaded is True

    def test_body_text_lazy_loaded(self, sample_export_page):
        from audit_rules.context import PageContext
        ctx = PageContext.from_export(sample_export_page)
        text = ctx.body_text
        assert text == "Test Content here"

    def test_response_headers_lazy_loaded(self, sample_export_page):
        from audit_rules.context import PageContext
        ctx = PageContext.from_export(sample_export_page)
        headers = ctx.response_headers
        assert headers == {"content-type": "text/html", "x-cache": "HIT"}

    def test_release_heavy_clears_fields(self, sample_export_page):
        from audit_rules.context import PageContext
        ctx = PageContext.from_export(sample_export_page)
        # Load first
        _ = ctx.body_html
        assert ctx._html_loaded is True
        # Release
        ctx.release_heavy()
        assert ctx._body_html is None
        assert ctx._body_text is None
        assert ctx._response_headers is None
        assert ctx._html_loaded is False

    def test_release_then_reaccess_lazy_loads_again(self, sample_export_page):
        from audit_rules.context import PageContext
        ctx = PageContext.from_export(sample_export_page)
        html1 = ctx.body_html
        ctx.release_heavy()
        html2 = ctx.body_html
        assert html1 == html2  # Same content, re-loaded

    def test_heavy_fields_default_none_without_export_data(self):
        """When _raw_export is None, heavy fields return None."""
        from audit_rules.context import PageContext
        ctx = PageContext(url="https://example.com")
        assert ctx.body_html is None
        assert ctx.body_text is None
        assert ctx.response_headers is None

    def test_heavy_fields_handle_missing_keys(self):
        """Export dict without body_html/body_text/response_headers."""
        from audit_rules.context import PageContext
        ctx = PageContext.from_export({"url": "https://example.com"})
        assert ctx.body_html is None
        assert ctx.body_text is None
        assert ctx.response_headers is None

    def test_heavy_fields_use_alt_key_names(self):
        """LibreCrawl may use 'html' / 'text' / 'headers' as keys."""
        from audit_rules.context import PageContext
        ctx = PageContext.from_export({
            "url": "https://example.com",
            "html": "<html>alt</html>",
            "text": "alt text",
            "headers": {"server": "nginx"},
        })
        assert ctx.body_html == "<html>alt</html>"
        assert ctx.body_text == "alt text"
        assert ctx.response_headers == {"server": "nginx"}


# ============================================================
# Test: PageContext — linked_from augmentation
# ============================================================

class TestPageContextInboundLinks:
    """Verify linked_from_count from linked_from list in export."""

    def test_linked_from_populated(self):
        from audit_rules.context import PageContext
        page = {
            "url": "https://example.com/target",
            "linked_from": ["https://a.com", "https://b.com", "https://c.com"],
        }
        ctx = PageContext.from_export(page)
        assert ctx.linked_from_count == 3

    def test_linked_from_missing_defaults_zero(self):
        from audit_rules.context import PageContext
        page = {"url": "https://example.com/target"}
        ctx = PageContext.from_export(page)
        assert ctx.linked_from_count == 0

    def test_linked_from_none_defaults_zero(self):
        from audit_rules.context import PageContext
        page = {"url": "https://example.com/target", "linked_from": None}
        ctx = PageContext.from_export(page)
        assert ctx.linked_from_count == 0


# ============================================================
# Test: PageContext — repr
# ============================================================

class TestPageContextRepr:
    def test_repr_includes_key_fields(self):
        from audit_rules.context import PageContext
        ctx = PageContext(url="https://example.com", status_code=200, word_count=450)
        r = repr(ctx)
        assert "https://example.com" in r
        assert "200" in r
        assert "450" in r

    def test_repr_does_not_trigger_heavy_load(self):
        """repr() must not trigger lazy loading of heavy fields."""
        from audit_rules.context import PageContext
        ctx = PageContext.from_export({
            "url": "https://example.com",
            "word_count": 100,
        })
        r = repr(ctx)
        assert ctx._html_loaded is False  # repr should not trigger heavy load


# ============================================================
# Test: SiteContext
# ============================================================

class TestSiteContext:
    """Verify SiteContext.from_site_check() production path."""

    def test_from_site_check_populates_robots_txt(self, sample_site_data):
        from audit_rules.context import SiteContext
        ctx = SiteContext.from_site_check(sample_site_data, "https://example.com")
        assert ctx.base_url == "https://example.com"
        assert ctx.robots_txt_found is True
        assert ctx.robots_txt_disallow_count == 3
        assert ctx.robots_txt_has_sitemap_declaration is True

    def test_from_site_check_populates_sitemap(self, sample_site_data):
        from audit_rules.context import SiteContext
        ctx = SiteContext.from_site_check(sample_site_data)
        assert ctx.sitemap_found is True
        assert ctx.sitemap_url == "https://example.com/sitemap.xml"
        assert ctx.sitemap_url_count == 45

    def test_from_site_check_populates_redirects(self, sample_site_data):
        from audit_rules.context import SiteContext
        ctx = SiteContext.from_site_check(sample_site_data)
        assert ctx.https_redirects is True
        assert ctx.www_redirects is False

    def test_from_site_check_accepts_production_redirect_keys(self):
        """The live site checker uses explicit production field names."""
        from audit_rules.context import SiteContext

        ctx = SiteContext.from_site_check({
            "https_redirect": {"http_redirects_to_https": True},
            "www_redirect": {"alt_redirects_properly": True},
        })

        assert ctx.https_redirects is True
        assert ctx.www_redirects is True

    def test_from_site_check_defaults_for_empty_data(self):
        from audit_rules.context import SiteContext
        ctx = SiteContext.from_site_check({})
        assert ctx.robots_txt_found is False
        assert ctx.robots_txt_disallow_count == 0
        assert ctx.sitemap_found is False
        assert ctx.sitemap_url is None
        assert ctx.https_redirects is False
        assert ctx.www_redirects is False

    def test_from_site_check_stores_raw_data(self, sample_site_data):
        from audit_rules.context import SiteContext
        ctx = SiteContext.from_site_check(sample_site_data)
        assert ctx._site_data is sample_site_data  # Reference, not copy


# ============================================================
# Test: LibreCrawlDataProvider
# ============================================================

class TestLibreCrawlDataProvider:
    """Verify LibreCrawlDataProvider.create_contexts()."""

    def test_create_contexts_builds_site_and_pages(self, sample_export_page, sample_site_data):
        from audit_rules.providers.librecrawl_provider import LibreCrawlDataProvider
        provider = LibreCrawlDataProvider(
            pages=[sample_export_page],
            site_data=sample_site_data,
            links=[],
        )
        site_ctx, page_ctxs = provider.create_contexts(base_url="https://example.com")

        assert len(page_ctxs) == 1
        assert page_ctxs[0].url == "https://example.com/page1"
        assert site_ctx.robots_txt_found is True
        assert site_ctx.sitemap_found is True

    def test_create_contexts_with_completeness(self, sample_export_page, sample_site_data, sample_completeness):
        from audit_rules.providers.librecrawl_provider import LibreCrawlDataProvider
        provider = LibreCrawlDataProvider(
            pages=[sample_export_page],
            site_data=sample_site_data,
            links=[],
        )
        site_ctx, _ = provider.create_contexts(
            base_url="https://example.com",
            completeness=sample_completeness,
        )
        assert site_ctx.pages_crawled == 45
        assert site_ctx.sitemap_total == 50
        assert site_ctx.sitemap_only_count == 5
        assert site_ctx.sitemap_coverage_pct == 90.0
        assert site_ctx.audit_complete is True

    def test_create_contexts_detects_wordpress(self, sample_site_data):
        from audit_rules.providers.librecrawl_provider import LibreCrawlDataProvider
        wp_page = {
            "url": "https://example.com/wp-content/uploads/img.jpg",
            "generator": "WordPress 6.5",
        }
        provider = LibreCrawlDataProvider(
            pages=[wp_page],
            site_data=sample_site_data,
            links=[],
        )
        site_ctx, _ = provider.create_contexts(base_url="https://example.com")
        assert site_ctx.site_profile == "wordpress"

    def test_create_contexts_detects_generic(self, sample_export_page, sample_site_data):
        from audit_rules.providers.librecrawl_provider import LibreCrawlDataProvider
        provider = LibreCrawlDataProvider(
            pages=[sample_export_page],
            site_data=sample_site_data,
            links=[],
        )
        site_ctx, _ = provider.create_contexts(base_url="https://example.com")
        assert site_ctx.site_profile == "generic"

    def test_create_contexts_augments_inbound_links(self, sample_export_page, sample_site_data):
        from audit_rules.providers.librecrawl_provider import LibreCrawlDataProvider
        links = [
            {"target_url": "https://example.com/page1", "source_url": "https://other.com"},
            {"target_url": "https://example.com/page1", "source_url": "https://another.com"},
        ]
        provider = LibreCrawlDataProvider(
            pages=[sample_export_page],
            site_data=sample_site_data,
            links=links,
        )
        _, page_ctxs = provider.create_contexts()
        # linked_from_count should be max of existing (2) and augmented (2)
        assert page_ctxs[0].linked_from_count == 2

    def test_provider_is_always_available(self):
        from audit_rules.providers.librecrawl_provider import LibreCrawlDataProvider
        provider = LibreCrawlDataProvider(pages=[], site_data={})
        assert provider.is_available() is True
        assert provider.name == "LibreCrawl"

    def test_create_contexts_empty_pages(self):
        from audit_rules.providers.librecrawl_provider import LibreCrawlDataProvider
        provider = LibreCrawlDataProvider(pages=[], site_data={})
        site_ctx, page_ctxs = provider.create_contexts()
        assert len(page_ctxs) == 0
        assert site_ctx.base_url == ""

    def test_create_contexts_with_alt_link_keys(self, sample_site_data):
        """Links may use 'to'/'from' instead of 'target_url'/'source_url'."""
        from audit_rules.providers.librecrawl_provider import LibreCrawlDataProvider
        page = {"url": "https://example.com/page1"}
        links = [
            {"to": "https://example.com/page1", "from": "https://other.com"},
        ]
        provider = LibreCrawlDataProvider(
            pages=[page],
            site_data=sample_site_data,
            links=links,
        )
        _, page_ctxs = provider.create_contexts()
        assert page_ctxs[0].linked_from_count >= 1

    def test_create_contexts_with_links_detailed_inbound(self, sample_site_data):
        """Per-page links_detailed also contributes to inbound map."""
        from audit_rules.providers.librecrawl_provider import LibreCrawlDataProvider
        page_a = {
            "url": "https://example.com/page-a",
            "links_detailed": [
                {"url": "https://example.com/page-b", "anchor": "B"},
            ],
        }
        page_b = {"url": "https://example.com/page-b"}
        provider = LibreCrawlDataProvider(
            pages=[page_a, page_b],
            site_data=sample_site_data,
            links=[],
        )
        _, page_ctxs = provider.create_contexts()
        # page_b should have linked_from_count from page_a's links_detailed
        page_b_ctx = [c for c in page_ctxs if c.url == "https://example.com/page-b"][0]
        assert page_b_ctx.linked_from_count >= 1
