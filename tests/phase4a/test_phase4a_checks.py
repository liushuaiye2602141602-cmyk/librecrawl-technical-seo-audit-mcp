"""Phase 4A — TDD Tests for 8 NEW_AUTO Stateless SEO Rules.

Tests cover:
  - Positive detection (real issues found → appropriate severity)
  - Negative / no-finding (clean pages → no false positive)
  - Edge cases (empty data, missing fields, boundary values)
  - False-positive gates (good pages must not produce ERROR/WARNING)

Rules tested:
  18 — Tags / Archives / Search Indexability
  32 — Image / Video Sitemap
  39 — WordPress XML-RPC / REST API Exposure
  43 — Sitemap lastmod Accuracy
  47 — Crawlable <a href> (Event-Only Navigation)
  51 — Internal Links → Redirect URLs
  60 — Multi-language Canonical
  67 — Staging / Dev Indexability
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Shared helpers
# ============================================================

def _make_page(**overrides) -> "PageContext":
    """Create a PageContext with sensible defaults, override any field."""
    from audit_rules.context import PageContext

    defaults = dict(
        url="https://example.com/",
        status_code=200,
        title="Test Page",
        meta_description="A test page",
        h1="Test Heading",
        canonical_url="https://example.com/",
        robots="index, follow",
        depth=1,
        word_count=500,
        internal_links_count=10,
        external_links_count=2,
        linked_from_count=3,
        json_ld_types=None,
        hreflang_summary=None,
        lang="en",
        links_detailed=[],
        image_summary={"count": 3, "broken": 0, "missing_alt": 1},
        _raw_export=None,
    )
    defaults.update(overrides)
    return PageContext(**defaults)


def _make_site(**overrides) -> "SiteContext":
    """Create a SiteContext with defaults."""
    from audit_rules.context import SiteContext

    defaults = dict(
        base_url="https://example.com",
        robots_txt_found=True,
        robots_txt_disallow_count=1,
        robots_txt_has_sitemap_declaration=True,
        sitemap_found=True,
        sitemap_url="https://example.com/sitemap.xml",
        sitemap_url_count=50,
        https_redirects=True,
        www_redirects=False,
    )
    defaults.update(overrides)
    return SiteContext(**defaults)


def _get_rule(audit_id: int):
    """Get a RuleDefinition from the registry by audit_id."""
    from audit_rules.registry import load_registry

    checklist = (
        PROJECT_ROOT
        / "audit_specs"
        / "technical_seo_master_checklist_80.csv"
    )
    mapping = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
    registry = load_registry(str(checklist), str(mapping))
    for r in registry:
        if r.audit_id == audit_id:
            return r
    raise ValueError(f"Rule {audit_id} not found in registry")


# ============================================================
# Rule 18 — Tags / Archives / Search Indexability
# ============================================================


class TestRule18ArchiveSearchIndexability:
    """Rule 18: Detect and report on CMS aggregation page indexability."""

    def test_search_results_indexable_reports_finding(self):
        """Search results page that is indexable → OPPORTUNITY."""
        from audit_rules.checks.phase4a_rules import check_archive_search_indexability

        rule = _get_rule(18)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/search?q=test",
                robots="index, follow",
            ),
        ]
        findings = check_archive_search_indexability(rule, site, pages, {})
        assert len(findings) >= 1
        f = findings[0]
        assert "search results" in f.detected_value.lower()
        assert "indexable" in f.detected_value.lower()

    def test_search_results_noindex_no_finding(self):
        """Search results page with noindex → no finding."""
        from audit_rules.checks.phase4a_rules import check_archive_search_indexability

        rule = _get_rule(18)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/search?q=test",
                robots="noindex, follow",
            ),
        ]
        findings = check_archive_search_indexability(rule, site, pages, {})
        assert len(findings) == 0

    def test_tag_page_auto_policy_reports_opportunity(self):
        """Tag page in auto mode → OPPORTUNITY with low confidence."""
        from audit_rules.checks.phase4a_rules import check_archive_search_indexability

        rule = _get_rule(18)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/tag/seo-tips",
                robots="index, follow",
                word_count=80,
            ),
        ]
        findings = check_archive_search_indexability(rule, site, pages, {})
        assert len(findings) >= 1
        f = findings[0]
        assert "auto" in f.detected_value.lower()
        assert f.confidence < 0.8  # Low confidence in auto mode

    def test_tag_page_noindex_policy_indexable_reports_warning(self):
        """Tag page that is indexable but policy=noindex → WARNING."""
        from audit_rules.checks.phase4a_rules import check_archive_search_indexability

        rule = _get_rule(18)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/tag/seo-tips",
                robots="index, follow",
            ),
        ]
        data = {"INDEXATION_POLICY_TAG": "noindex"}
        findings = check_archive_search_indexability(rule, site, pages, data)
        assert len(findings) >= 1
        f = findings[0]
        assert f.severity == "Warning"

    def test_author_page_detected(self):
        """Author archive page is classified correctly."""
        from audit_rules.checks.phase4a_rules import check_archive_search_indexability

        rule = _get_rule(18)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/author/john-doe",
                robots="index, follow",
            ),
        ]
        findings = check_archive_search_indexability(rule, site, pages, {})
        assert len(findings) >= 1
        assert "author" in findings[0].detected_value.lower()

    def test_category_page_index_policy_ok(self):
        """Category page with policy=index → INFO (no warning)."""
        from audit_rules.checks.phase4a_rules import check_archive_search_indexability

        rule = _get_rule(18)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/category/tech",
                robots="index, follow",
                word_count=300,
            ),
        ]
        data = {"INDEXATION_POLICY_CATEGORY": "index"}
        findings = check_archive_search_indexability(rule, site, pages, {**data})
        assert len(findings) >= 1
        assert findings[0].severity in ("Info", "Opportunity")

    def test_date_archive_detected(self):
        """Date archive URL like /2024/03/ is detected."""
        from audit_rules.checks.phase4a_rules import check_archive_search_indexability

        rule = _get_rule(18)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/2024/03/",
                robots="index, follow",
            ),
        ]
        findings = check_archive_search_indexability(rule, site, pages, {})
        assert len(findings) >= 1
        assert "date_archive" in findings[0].detected_value.lower()

    def test_normal_page_no_finding(self):
        """Regular blog post is not flagged as archive."""
        from audit_rules.checks.phase4a_rules import check_archive_search_indexability

        rule = _get_rule(18)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/blog/my-article",
                robots="index, follow",
            ),
        ]
        findings = check_archive_search_indexability(rule, site, pages, {})
        assert len(findings) == 0

    def test_non_200_pages_skipped(self):
        """404 and redirect pages are skipped."""
        from audit_rules.checks.phase4a_rules import check_archive_search_indexability

        rule = _get_rule(18)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/tag/seo",
                status_code=404,
            ),
        ]
        findings = check_archive_search_indexability(rule, site, pages, {})
        assert len(findings) == 0

    def test_empty_page_list_no_error(self):
        """Empty page list → no findings, no crash."""
        from audit_rules.checks.phase4a_rules import check_archive_search_indexability

        rule = _get_rule(18)
        site = _make_site()
        findings = check_archive_search_indexability(rule, site, [], {})
        assert findings == []


# ============================================================
# Rule 32 — Image / Video Sitemap
# ============================================================


class TestRule32MediaSitemap:
    """Rule 32: Check for image/video sitemap presence."""

    def test_image_heavy_no_sitemap_opportunity(self):
        """Site with many images but no image sitemap → OPPORTUNITY."""
        from audit_rules.checks.phase4a_rules import check_media_sitemap

        rule = _get_rule(32)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/gallery",
                image_summary={"count": 25, "broken": 0, "missing_alt": 5},
            ),
        ]
        data = {"sitemap_data": {"raw": "<urlset><url><loc>https://example.com</loc></url></urlset>"}}
        findings = check_media_sitemap(rule, site, pages, data)
        # Image count > 10, no image sitemap → OPPORTUNITY
        assert len(findings) >= 1
        assert any("image" in f.detected_value.lower() for f in findings)

    def test_video_pages_no_sitemap_opportunity(self):
        """Pages with video schema but no video sitemap → OPPORTUNITY."""
        from audit_rules.checks.phase4a_rules import check_media_sitemap

        rule = _get_rule(32)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/video-page",
                json_ld_types=["VideoObject", "WebPage"],
            ),
        ]
        findings = check_media_sitemap(rule, site, pages, {})
        assert any("video" in f.detected_value.lower() for f in findings)

    def test_no_media_not_applicable(self):
        """Site with no images/videos → INFO (not applicable)."""
        from audit_rules.checks.phase4a_rules import check_media_sitemap

        rule = _get_rule(32)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/text-only",
                image_summary={"count": 0, "broken": 0, "missing_alt": 0},
            ),
        ]
        findings = check_media_sitemap(rule, site, pages, {})
        assert len(findings) >= 1
        assert findings[0].severity == "Info"
        assert "not applicable" in findings[0].detected_value.lower()

    def test_image_sitemap_present_no_finding(self):
        """Site with image sitemap → no finding about missing it."""
        from audit_rules.checks.phase4a_rules import check_media_sitemap

        rule = _get_rule(32)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/gallery",
                image_summary={"count": 20, "broken": 0, "missing_alt": 2},
            ),
        ]
        data = {"sitemap_data": {"raw": (
            '<urlset xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">'
            '<url><loc>https://example.com</loc>'
            '<image:image><image:loc>https://example.com/img.jpg</image:loc></image:image>'
            '</url></urlset>'
        )}}
        findings = check_media_sitemap(rule, site, pages, data)
        # Has image sitemap - no "missing image sitemap" finding
        img_findings = [f for f in findings if "image sitemap" in f.detected_value.lower() and "no image" in f.detected_value.lower()]
        assert len(img_findings) == 0

    def test_empty_sitemap_data_no_crash(self):
        """No sitemap data → no crash."""
        from audit_rules.checks.phase4a_rules import check_media_sitemap

        rule = _get_rule(32)
        site = _make_site()
        pages = [_make_page()]
        findings = check_media_sitemap(rule, site, pages, {})
        # Should not crash; may produce findings or be empty
        assert isinstance(findings, list)

    def test_low_image_count_no_false_positive(self):
        """Few images (≤10) should not trigger image sitemap missing report."""
        from audit_rules.checks.phase4a_rules import check_media_sitemap

        rule = _get_rule(32)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/about",
                image_summary={"count": 5, "broken": 0, "missing_alt": 0},
            ),
        ]
        findings = check_media_sitemap(rule, site, pages, {})
        img_findings = [f for f in findings if "image sitemap" in f.detected_value.lower() and "no image" in f.detected_value.lower()]
        assert len(img_findings) == 0


# ============================================================
# Rule 39 — WordPress XML-RPC / REST API Exposure
# ============================================================


class TestRule39WordPressAPIExposure:
    """Rule 39: WordPress XML-RPC / REST API exposure assessment.

    No HTTP probes — crawl signals only (WP_SECURITY_PROBES_ENABLED default false).
    """

    def test_non_wp_site_no_findings(self):
        """Non-WordPress site → no findings."""
        from audit_rules.checks.phase4a_rules import check_wordpress_api_exposure

        rule = _get_rule(39)
        site = _make_site()
        pages = [_make_page(url="https://example.com/about")]
        findings = check_wordpress_api_exposure(rule, site, pages, {})
        assert len(findings) == 0

    def test_wp_site_xmlrpc_detected(self):
        """WordPress site with xmlrpc.php in crawl → INFO."""
        from audit_rules.checks.phase4a_rules import check_wordpress_api_exposure

        rule = _get_rule(39)
        site = _make_site(base_url="https://example.com")
        pages = [
            _make_page(url="https://example.com/"),
            _make_page(url="https://example.com/xmlrpc.php"),
            _make_page(url="https://example.com/wp-content/uploads/img.jpg"),
            _make_page(url="https://example.com/blog-post"),
        ]
        # Also add a link pointing to xmlrpc.php to ensure enough WP signals
        pages[0].links_detailed = [
            {"url": "https://example.com/wp-content/themes/style.css", "anchor": "", "is_internal": True},
        ]
        data = {"site_check": {"generator": "WordPress 6.4"}}
        findings = check_wordpress_api_exposure(rule, site, pages, data)
        xmlrpc_findings = [f for f in findings if "xmlrpc" in f.detected_value.lower()]
        assert len(xmlrpc_findings) >= 1
        assert xmlrpc_findings[0].severity == "Info"

    def test_wp_rest_users_exposed_warning(self):
        """WordPress REST API user endpoint exposed → WARNING."""
        from audit_rules.checks.phase4a_rules import check_wordpress_api_exposure

        rule = _get_rule(39)
        site = _make_site(base_url="https://example.com")
        pages = [
            _make_page(url="https://example.com/"),
            _make_page(
                url="https://example.com/wp-json/wp/v2/users",
            ),
            _make_page(url="https://example.com/wp-content/uploads/img.jpg"),
            _make_page(url="https://example.com/wp-includes/js/wp-embed.min.js"),
        ]
        data = {"site_check": {"generator": "WordPress 6.4"}}
        findings = check_wordpress_api_exposure(rule, site, pages, data)
        rest_findings = [f for f in findings if "rest api" in f.detected_value.lower() or "/wp-json" in f.detected_value.lower()]
        assert len(rest_findings) >= 1

    def test_wp_detected_no_sensitive_exposure_info(self):
        """WordPress detected, REST API exists but no sensitive exposure → INFO."""
        from audit_rules.checks.phase4a_rules import check_wordpress_api_exposure

        rule = _get_rule(39)
        site = _make_site(base_url="https://example.com")
        pages = [
            _make_page(url="https://example.com/"),
            _make_page(url="https://example.com/wp-json/"),
            _make_page(url="https://example.com/wp-content/themes/style.css"),
            _make_page(url="https://example.com/blog-post"),
        ]
        data = {"site_check": {"generator": "WordPress 6.4"}}
        findings = check_wordpress_api_exposure(rule, site, pages, data)
        # Should have at least 1 finding about WP being detected
        assert len(findings) >= 1

    def test_no_false_positive_non_wp(self):
        """A static site with no WP signals → no findings."""
        from audit_rules.checks.phase4a_rules import check_wordpress_api_exposure

        rule = _get_rule(39)
        site = _make_site()
        pages = [
            _make_page(url="https://example.com/"),
            _make_page(url="https://example.com/about"),
            _make_page(url="https://example.com/contact"),
        ]
        findings = check_wordpress_api_exposure(rule, site, pages, {})
        assert len(findings) == 0

    def test_wp_from_links_not_urls(self):
        """WordPress detected from internal links (not page URLs)."""
        from audit_rules.checks.phase4a_rules import check_wordpress_api_exposure

        rule = _get_rule(39)
        site = _make_site(base_url="https://example.com")
        pages = [
            _make_page(
                url="https://example.com/",
                links_detailed=[
                    {"url": "https://example.com/wp-content/themes/style.css", "anchor": "", "is_internal": True},
                    {"url": "https://example.com/wp-json/", "anchor": "API", "is_internal": True},
                    {"url": "https://example.com/wp-admin/", "anchor": "Admin", "is_internal": True},
                ],
            ),
            _make_page(url="https://example.com/about"),
        ]
        findings = check_wordpress_api_exposure(rule, site, pages, {})
        # WP signals from links + maybe REST API → at least detected
        assert len(findings) >= 1


# ============================================================
# Rule 43 — Sitemap lastmod Accuracy
# ============================================================


class TestRule43SitemapLastmod:
    """Rule 43: Validate sitemap lastmod fields."""

    def test_invalid_date_format_warning(self):
        """Invalid W3C datetime → WARNING."""
        from audit_rules.checks.phase4a_rules import check_sitemap_lastmod

        rule = _get_rule(43)
        site = _make_site()
        data = {
            "sitemap_urls": [
                {"loc": "https://example.com/page1", "lastmod": "not-a-date"},
                {"loc": "https://example.com/page2", "lastmod": "2024-01-15"},
            ],
        }
        findings = check_sitemap_lastmod(rule, site, [], data)
        assert len(findings) >= 1
        assert any("invalid" in f.detected_value.lower() for f in findings)

    def test_future_date_warning(self):
        """Future dates → WARNING."""
        from audit_rules.checks.phase4a_rules import check_sitemap_lastmod

        rule = _get_rule(43)
        site = _make_site()
        data = {
            "sitemap_urls": [
                {"loc": "https://example.com/page1", "lastmod": "2099-12-31"},
            ],
        }
        findings = check_sitemap_lastmod(rule, site, [], data)
        assert len(findings) >= 1
        assert any("future" in f.detected_value.lower() for f in findings)

    def test_all_same_date_today_warning(self):
        """All URLs same date = today → WARNING (mass-refresh)."""
        from audit_rules.checks.phase4a_rules import check_sitemap_lastmod
        from datetime import datetime, timezone

        rule = _get_rule(43)
        site = _make_site()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        urls = []
        for i in range(10):
            urls.append({"loc": f"https://example.com/page{i}", "lastmod": today})
        data = {"sitemap_urls": urls}
        findings = check_sitemap_lastmod(rule, site, [], data)
        assert len(findings) >= 1
        mass_refresh = [f for f in findings if "same-date" in f.detected_value.lower() or "today" in f.finding_detail.lower()]
        assert len(mass_refresh) >= 1

    def test_clean_dates_no_finding(self):
        """Valid, diverse dates → no findings."""
        from audit_rules.checks.phase4a_rules import check_sitemap_lastmod

        rule = _get_rule(43)
        site = _make_site()
        urls = []
        for i in range(20):
            urls.append({"loc": f"https://example.com/page{i}", "lastmod": f"2024-{1 + i % 12:02d}-{1 + i % 28:02d}"})
        data = {"sitemap_urls": urls}
        findings = check_sitemap_lastmod(rule, site, [], data)
        # No invalid, no future, diverse dates → clean
        assert all("invalid" not in f.detected_value.lower() for f in findings)
        assert all("future" not in f.detected_value.lower() for f in findings)

    def test_no_sitemap_data_no_findings(self):
        """No sitemap data available → no findings."""
        from audit_rules.checks.phase4a_rules import check_sitemap_lastmod

        rule = _get_rule(43)
        site = _make_site()
        findings = check_sitemap_lastmod(rule, site, [], {})
        assert len(findings) == 0

    def test_all_same_date_not_today_opportunity(self):
        """All same date but not today → OPPORTUNITY (less urgent)."""
        from audit_rules.checks.phase4a_rules import check_sitemap_lastmod

        rule = _get_rule(43)
        site = _make_site()
        urls = []
        for i in range(10):
            urls.append({"loc": f"https://example.com/page{i}", "lastmod": "2024-06-15"})
        data = {"sitemap_urls": urls}
        findings = check_sitemap_lastmod(rule, site, [], data)
        assert len(findings) >= 1
        same_date = [f for f in findings if "same-date" in f.detected_value.lower()]
        assert len(same_date) >= 1
        assert same_date[0].severity == "Opportunity"

    def test_sitemap_urls_via_extended_checks(self):
        """Sitemap data via extended_checks path is found."""
        from audit_rules.checks.phase4a_rules import check_sitemap_lastmod

        rule = _get_rule(43)
        site = _make_site()
        data = {
            "extended_checks": {
                "sitemap": {
                    "urls": [
                        {"loc": "https://example.com/page1", "lastmod": "invalid-date-here"},
                    ],
                },
            },
        }
        findings = check_sitemap_lastmod(rule, site, [], data)
        assert len(findings) >= 1
        assert any("invalid" in f.detected_value.lower() for f in findings)

    def test_iso8601_with_timezone_parsed(self):
        """ISO 8601 with timezone offset is parsed correctly."""
        from audit_rules.checks.phase4a_rules import check_sitemap_lastmod

        rule = _get_rule(43)
        site = _make_site()
        urls = []
        for i in range(15):
            urls.append({
                "loc": f"https://example.com/page{i}",
                "lastmod": f"2024-{1 + i % 12:02d}-{1 + i % 28:02d}T09:30:00+00:00",
            })
        data = {"sitemap_urls": urls}
        findings = check_sitemap_lastmod(rule, site, [], data)
        # All valid ISO 8601 with timezone — no invalid findings
        assert all("invalid" not in f.detected_value.lower() for f in findings)

    def test_few_entries_no_false_mass_refresh(self):
        """Few entries (< 5) with same date → no mass-refresh flag."""
        from audit_rules.checks.phase4a_rules import check_sitemap_lastmod

        rule = _get_rule(43)
        site = _make_site()
        urls = [
            {"loc": "https://example.com/page1", "lastmod": "2024-06-15"},
            {"loc": "https://example.com/page2", "lastmod": "2024-06-15"},
            {"loc": "https://example.com/page3", "lastmod": "2024-06-15"},
        ]
        data = {"sitemap_urls": urls}
        findings = check_sitemap_lastmod(rule, site, [], data)
        same_date = [f for f in findings if "same-date" in f.detected_value.lower()]
        assert len(same_date) == 0


# ============================================================
# Rule 47 — Crawlable <a href> (Event-Only Navigation)
# ============================================================


class TestRule47CrawlableLinks:
    """Rule 47: Detect event-only navigation without <a href>."""

    def test_onclick_navigation_detected(self):
        """onclick-based navigation without proper href → detected."""
        from audit_rules.checks.phase4a_rules import check_crawlable_links

        rule = _get_rule(47)
        site = _make_site()
        html = (
            '<a href="/about">About</a>'
            '<a href="/contact">Contact</a>'
            '<a onclick="location.href=\'/products\'" style="cursor:pointer">Products</a>'
            '<a onclick="window.location=\'/services\'" style="cursor:pointer">Services</a>'
        )
        pages = [
            _make_page(
                url="https://example.com/",
                _raw_export={"html": html},
            ),
        ]
        findings = check_crawlable_links(rule, site, pages, {})
        assert len(findings) >= 1
        assert "navigation elements" in findings[0].detected_value.lower()

    def test_data_href_without_anchor_detected(self):
        """data-href on div/span without <a> wrapper → detected."""
        from audit_rules.checks.phase4a_rules import check_crawlable_links

        rule = _get_rule(47)
        site = _make_site()
        html = (
            '<a href="/page1">Page 1</a>'
            '<div data-href="/page2" onclick="navigate()">Page 2</div>'
            '<span data-href="/page3" class="card-link">Page 3</span>'
        )
        pages = [
            _make_page(
                url="https://example.com/",
                _raw_export={"html": html},
            ),
        ]
        findings = check_crawlable_links(rule, site, pages, {})
        assert len(findings) >= 1

    def test_all_crawlable_no_finding(self):
        """Page with all standard <a href> links → no finding."""
        from audit_rules.checks.phase4a_rules import check_crawlable_links

        rule = _get_rule(47)
        site = _make_site()
        html = (
            '<a href="/home">Home</a>'
            '<a href="/about">About</a>'
            '<a href="/blog/post-1">Blog Post</a>'
            '<a href="/contact">Contact</a>'
        )
        pages = [
            _make_page(
                url="https://example.com/",
                _raw_export={"html": html},
            ),
        ]
        findings = check_crawlable_links(rule, site, pages, {})
        assert len(findings) == 0

    def test_no_html_no_finding(self):
        """Page with no HTML available → no finding."""
        from audit_rules.checks.phase4a_rules import check_crawlable_links

        rule = _get_rule(47)
        site = _make_site()
        pages = [
            _make_page(url="https://example.com/", _raw_export=None),
        ]
        findings = check_crawlable_links(rule, site, pages, {})
        assert len(findings) == 0

    def test_non_200_pages_skipped(self):
        """Non-200 pages are not analyzed."""
        from audit_rules.checks.phase4a_rules import check_crawlable_links

        rule = _get_rule(47)
        site = _make_site()
        html = '<a onclick="location.href=\'/bad\'">Go</a>'
        pages = [
            _make_page(
                url="https://example.com/",
                status_code=404,
                _raw_export={"html": html},
            ),
        ]
        findings = check_crawlable_links(rule, site, pages, {})
        assert len(findings) == 0

    def test_single_event_only_opportunity(self):
        """One event-only link → OPPORTUNITY, not WARNING."""
        from audit_rules.checks.phase4a_rules import check_crawlable_links

        rule = _get_rule(47)
        site = _make_site()
        html = (
            '<a href="/page1">P1</a>'
            '<a onclick="location.href=\'/special\'">Special</a>'
        )
        pages = [
            _make_page(
                url="https://example.com/",
                _raw_export={"html": html},
            ),
        ]
        findings = check_crawlable_links(rule, site, pages, {})
        if findings:
            assert findings[0].severity == "Opportunity"


# ============================================================
# Rule 51 — Internal Links → Redirect URLs
# ============================================================


class TestRule51InternalRedirectLinks:
    """Rule 51: Detect internal links pointing to redirect (3xx) URLs."""

    def test_link_to_301_redirect_opportunity(self):
        """Internal link to 301 page → OPPORTUNITY."""
        from audit_rules.checks.phase4a_rules import check_internal_redirect_links

        rule = _get_rule(51)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/",
                status_code=200,
                links_detailed=[
                    {"url": "https://example.com/old-page", "anchor": "Old Page", "is_internal": True},
                ],
            ),
            _make_page(
                url="https://example.com/old-page",
                status_code=301,
                canonical_url="https://example.com/new-page",
            ),
        ]
        findings = check_internal_redirect_links(rule, site, pages, {})
        assert len(findings) >= 1
        assert "redirect" in findings[0].detected_value.lower() or "301" in findings[0].detected_value

    def test_link_to_404_warning(self):
        """Internal link to 404 page → WARNING."""
        from audit_rules.checks.phase4a_rules import check_internal_redirect_links

        rule = _get_rule(51)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/",
                status_code=200,
                links_detailed=[
                    {"url": "https://example.com/deleted-page", "anchor": "Deleted", "is_internal": True},
                ],
            ),
            _make_page(
                url="https://example.com/deleted-page",
                status_code=404,
            ),
        ]
        findings = check_internal_redirect_links(rule, site, pages, {})
        assert len(findings) >= 1
        assert "404" in findings[0].detected_value

    def test_clean_links_no_finding(self):
        """All internal links point to 200 pages → no findings."""
        from audit_rules.checks.phase4a_rules import check_internal_redirect_links

        rule = _get_rule(51)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/",
                status_code=200,
                links_detailed=[
                    {"url": "https://example.com/about", "anchor": "About", "is_internal": True},
                    {"url": "https://example.com/contact", "anchor": "Contact", "is_internal": True},
                ],
            ),
            _make_page(url="https://example.com/about", status_code=200),
            _make_page(url="https://example.com/contact", status_code=200),
        ]
        findings = check_internal_redirect_links(rule, site, pages, {})
        assert len(findings) == 0

    def test_external_links_ignored(self):
        """External links are not checked (only internal)."""
        from audit_rules.checks.phase4a_rules import check_internal_redirect_links

        rule = _get_rule(51)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/",
                status_code=200,
                links_detailed=[
                    {"url": "https://external.com/broken", "anchor": "External", "is_internal": False},
                ],
            ),
        ]
        findings = check_internal_redirect_links(rule, site, pages, {})
        assert len(findings) == 0

    def test_no_links_no_finding(self):
        """Page with no links → no findings."""
        from audit_rules.checks.phase4a_rules import check_internal_redirect_links

        rule = _get_rule(51)
        site = _make_site()
        pages = [
            _make_page(url="https://example.com/", links_detailed=[]),
        ]
        findings = check_internal_redirect_links(rule, site, pages, {})
        assert len(findings) == 0

    def test_302_redirect_detected(self):
        """302 temporary redirect also detected."""
        from audit_rules.checks.phase4a_rules import check_internal_redirect_links

        rule = _get_rule(51)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/",
                status_code=200,
                links_detailed=[
                    {"url": "https://example.com/temp-redirect", "anchor": "Temp", "is_internal": True},
                ],
            ),
            _make_page(
                url="https://example.com/temp-redirect",
                status_code=302,
                canonical_url="https://example.com/final",
            ),
        ]
        findings = check_internal_redirect_links(rule, site, pages, {})
        assert len(findings) >= 1
        assert "302" in findings[0].detected_value


# ============================================================
# Rule 60 — Multi-language Canonical
# ============================================================


class TestRule60MultilingualCanonical:
    """Rule 60: Detect cross-language canonical issues."""

    def test_cross_language_canonical_warning(self):
        """/de/ page canonical → /en/ page → WARNING."""
        from audit_rules.checks.phase4a_rules import check_multilang_canonical

        rule = _get_rule(60)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/de/ueber-uns",
                canonical_url="https://example.com/en/about-us",
                lang="de",
            ),
            _make_page(
                url="https://example.com/en/about-us",
                canonical_url="https://example.com/en/about-us",
                lang="en",
            ),
        ]
        findings = check_multilang_canonical(rule, site, pages, {})
        assert len(findings) >= 1
        assert "cross-language" in findings[0].detected_value.lower()
        assert findings[0].severity == "Warning"

    def test_self_canonical_no_finding(self):
        """Self-referencing canonical → no finding."""
        from audit_rules.checks.phase4a_rules import check_multilang_canonical

        rule = _get_rule(60)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/en/about",
                canonical_url="https://example.com/en/about",
                lang="en",
            ),
        ]
        findings = check_multilang_canonical(rule, site, pages, {})
        assert len(findings) == 0

    def test_same_language_canonical_no_finding(self):
        """Canonical in same language → no finding."""
        from audit_rules.checks.phase4a_rules import check_multilang_canonical

        rule = _get_rule(60)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/en/article-old",
                canonical_url="https://example.com/en/article-new",
                lang="en",
            ),
        ]
        findings = check_multilang_canonical(rule, site, pages, {})
        assert len(findings) == 0

    def test_regional_variant_no_false_positive(self):
        """en-us → en-gb with hreflang cluster → no finding (regional, not cross-language)."""
        from audit_rules.checks.phase4a_rules import check_multilang_canonical

        rule = _get_rule(60)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/en-us/page",
                canonical_url="https://example.com/en-gb/page",
                lang="en-US",
                hreflang_summary=[
                    {"lang": "en-US", "url": "https://example.com/en-us/page"},
                    {"lang": "en-GB", "url": "https://example.com/en-gb/page"},
                    {"lang": "x-default", "url": "https://example.com/en-gb/page"},
                ],
            ),
            _make_page(
                url="https://example.com/en-gb/page",
                canonical_url="https://example.com/en-gb/page",
                lang="en-GB",
                hreflang_summary=[
                    {"lang": "en-US", "url": "https://example.com/en-us/page"},
                    {"lang": "en-GB", "url": "https://example.com/en-gb/page"},
                    {"lang": "x-default", "url": "https://example.com/en-gb/page"},
                ],
            ),
        ]
        findings = check_multilang_canonical(rule, site, pages, {})
        assert len(findings) == 0

    def test_no_canonical_no_finding(self):
        """Page without canonical → no finding."""
        from audit_rules.checks.phase4a_rules import check_multilang_canonical

        rule = _get_rule(60)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/de/page",
                canonical_url="",
                lang="de",
            ),
        ]
        findings = check_multilang_canonical(rule, site, pages, {})
        assert len(findings) == 0

    def test_language_from_url_path(self):
        """Language detected from URL path (/fr/page)."""
        from audit_rules.checks.phase4a_rules import check_multilang_canonical

        rule = _get_rule(60)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/fr/produits",
                canonical_url="https://example.com/en/products",
                lang="",  # No HTML lang
            ),
        ]
        findings = check_multilang_canonical(rule, site, pages, {})
        assert len(findings) >= 1
        assert "cross-language" in findings[0].detected_value.lower()

    def test_non_200_pages_skipped(self):
        """Non-200 pages are not analyzed."""
        from audit_rules.checks.phase4a_rules import check_multilang_canonical

        rule = _get_rule(60)
        site = _make_site()
        pages = [
            _make_page(
                url="https://example.com/de/page",
                status_code=404,
                canonical_url="https://example.com/en/page",
                lang="de",
            ),
        ]
        findings = check_multilang_canonical(rule, site, pages, {})
        assert len(findings) == 0


# ============================================================
# Rule 67 — Staging / Dev Indexability
# ============================================================


class TestRule67StagingIndexability:
    """Rule 67: Detect staging/dev environment indexability.

    Does NOT brute-force, scan DNS, or guess hostnames.
    """

    def test_staging_hostname_indexable_error(self):
        """Current audit is on a staging hostname that's indexable → ERROR."""
        from audit_rules.checks.phase4a_rules import check_staging_indexability

        rule = _get_rule(67)
        site = _make_site(base_url="https://staging.example.com")
        pages = [
            _make_page(
                url="https://staging.example.com/",
                robots="index, follow",
            ),
        ]
        findings = check_staging_indexability(rule, site, pages, {})
        error_findings = [f for f in findings if f.severity == "Error"]
        assert len(error_findings) >= 1
        assert "staging" in error_findings[0].detected_value.lower()

    def test_staging_url_in_internal_links(self):
        """Internal link points to a staging domain → WARNING."""
        from audit_rules.checks.phase4a_rules import check_staging_indexability

        rule = _get_rule(67)
        site = _make_site(base_url="https://example.com")
        pages = [
            _make_page(
                url="https://example.com/",
                links_detailed=[
                    {"url": "https://staging.example.com/", "anchor": "Staging", "is_internal": False},
                ],
            ),
        ]
        findings = check_staging_indexability(rule, site, pages, {})
        assert len(findings) >= 1
        staging_findings = [f for f in findings if "staging" in f.detected_value.lower()]
        assert len(staging_findings) >= 1

    def test_no_staging_candidates_info(self):
        """No staging candidates → INFO with low confidence."""
        from audit_rules.checks.phase4a_rules import check_staging_indexability

        rule = _get_rule(67)
        site = _make_site(base_url="https://example.com")
        pages = [
            _make_page(url="https://example.com/"),
            _make_page(url="https://example.com/about"),
        ]
        findings = check_staging_indexability(rule, site, pages, {})
        assert len(findings) == 1
        assert findings[0].severity == "Info"
        assert findings[0].confidence < 0.5

    def test_staging_in_canonical_detected(self):
        """Staging URL in canonical tag → candidate found."""
        from audit_rules.checks.phase4a_rules import check_staging_indexability

        rule = _get_rule(67)
        site = _make_site(base_url="https://example.com")
        pages = [
            _make_page(
                url="https://example.com/page",
                canonical_url="https://dev.example.com/page",
            ),
        ]
        findings = check_staging_indexability(rule, site, pages, {})
        assert len(findings) >= 1
        assert any("dev.example.com" in f.evidence for f in findings)

    def test_user_configured_staging_urls(self):
        """User-configured STAGING_URLS are checked."""
        from audit_rules.checks.phase4a_rules import check_staging_indexability

        rule = _get_rule(67)
        site = _make_site(base_url="https://example.com")
        pages = [_make_page(url="https://example.com/")]
        data = {"STAGING_URLS": ["https://preview.example.com"]}
        findings = check_staging_indexability(rule, site, pages, data)
        assert len(findings) >= 1
        assert any("preview.example.com" in f.evidence for f in findings)

    def test_staging_hostname_not_indexable_no_error(self):
        """Staging hostname but not indexable → no ERROR finding."""
        from audit_rules.checks.phase4a_rules import check_staging_indexability

        rule = _get_rule(67)
        site = _make_site(base_url="https://dev.example.com")
        pages = [
            _make_page(
                url="https://dev.example.com/",
                robots="noindex, nofollow",
            ),
        ]
        findings = check_staging_indexability(rule, site, pages, {})
        error_findings = [f for f in findings if f.severity == "Error"]
        assert len(error_findings) == 0

    def test_wpengine_domain_detected(self):
        """*.wpengine.com staging domain → detected."""
        from audit_rules.checks.phase4a_rules import check_staging_indexability

        rule = _get_rule(67)
        site = _make_site(base_url="https://mysite.wpengine.com")
        pages = [
            _make_page(
                url="https://mysite.wpengine.com/",
                robots="index, follow",
            ),
        ]
        findings = check_staging_indexability(rule, site, pages, {})
        error_findings = [f for f in findings if f.severity == "Error"]
        assert len(error_findings) >= 1

    def test_staging_in_hreflang_detected(self):
        """Staging URL in hreflang tag → candidate found."""
        from audit_rules.checks.phase4a_rules import check_staging_indexability

        rule = _get_rule(67)
        site = _make_site(base_url="https://example.com")
        pages = [
            _make_page(
                url="https://example.com/",
                hreflang_summary=[
                    {"lang": "en", "url": "https://staging.example.com/"},
                ],
            ),
        ]
        findings = check_staging_indexability(rule, site, pages, {})
        assert len(findings) >= 1
        assert any("staging" in f.evidence.lower() for f in findings)


# ============================================================
# False-Positive Protection (all rules)
# ============================================================


class TestPhase4AFalsePositiveProtection:
    """Clean/good pages must NOT produce ERROR or WARNING findings."""

    def _get_all_check_functions(self):
        from audit_rules.checks.phase4a_rules import (
            check_archive_search_indexability,
            check_media_sitemap,
            check_wordpress_api_exposure,
            check_sitemap_lastmod,
            check_crawlable_links,
            check_internal_redirect_links,
            check_multilang_canonical,
            check_staging_indexability,
        )
        return {
            "check_archive_search_indexability": check_archive_search_indexability,
            "check_media_sitemap": check_media_sitemap,
            "check_wordpress_api_exposure": check_wordpress_api_exposure,
            "check_sitemap_lastmod": check_sitemap_lastmod,
            "check_crawlable_links": check_crawlable_links,
            "check_internal_redirect_links": check_internal_redirect_links,
            "check_multilang_canonical": check_multilang_canonical,
            "check_staging_indexability": check_staging_indexability,
        }

    def make_clean_pages(self):
        """Pages that should produce no ERROR/WARNING findings across all rules."""
        return [
            _make_page(
                url="https://example.com/",
                canonical_url="https://example.com/",
                robots="index, follow",
                lang="en",
                links_detailed=[
                    {"url": "https://example.com/about", "anchor": "About", "is_internal": True},
                    {"url": "https://example.com/contact", "anchor": "Contact", "is_internal": True},
                ],
                _raw_export={"html": (
                    '<a href="/about">About</a>'
                    '<a href="/contact">Contact</a>'
                )},
            ),
            _make_page(
                url="https://example.com/about",
                canonical_url="https://example.com/about",
                robots="index, follow",
                lang="en",
                _raw_export={"html": '<a href="/">Home</a>'},
            ),
            _make_page(
                url="https://example.com/contact",
                canonical_url="https://example.com/contact",
                robots="index, follow",
                lang="en",
                _raw_export={"html": '<a href="/">Home</a>'},
            ),
        ]

    def test_no_error_or_warning_on_clean_site_rule18(self):
        """Clean pages → no ERROR/WARNING for archive/search rule."""
        from audit_rules.checks.phase4a_rules import check_archive_search_indexability

        rule = _get_rule(18)
        site = _make_site()
        pages = self.make_clean_pages()
        findings = check_archive_search_indexability(rule, site, pages, {})
        bad = [f for f in findings if f.severity in ("Error", "Warning")]
        assert len(bad) == 0, f"False positive: {bad}"

    def test_no_error_or_warning_on_clean_site_rule47(self):
        """Clean pages with proper <a href> → no finding from Rule 47."""
        from audit_rules.checks.phase4a_rules import check_crawlable_links

        rule = _get_rule(47)
        site = _make_site()
        pages = self.make_clean_pages()
        findings = check_crawlable_links(rule, site, pages, {})
        bad = [f for f in findings if f.severity in ("Error", "Warning")]
        assert len(bad) == 0, f"False positive: {bad}"

    def test_no_error_or_warning_on_clean_site_rule51(self):
        """Clean internal links → no finding from Rule 51."""
        from audit_rules.checks.phase4a_rules import check_internal_redirect_links

        rule = _get_rule(51)
        site = _make_site()
        pages = self.make_clean_pages()
        findings = check_internal_redirect_links(rule, site, pages, {})
        bad = [f for f in findings if f.severity in ("Error", "Warning")]
        assert len(bad) == 0, f"False positive: {bad}"


# ============================================================
# Classification Integrity
# ============================================================


class TestPhase4AClassificationIntegrity:
    """Phase 4A rule classification must match CSV source of truth."""

    def test_phase4a_rules_now_existing_partial(self):
        """All 8 Phase 4A rules are now EXISTING_PARTIAL (migrated from NEW_AUTO)."""
        import csv

        csv_path = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        phase4a_ids = {18, 32, 39, 43, 47, 51, 60, 67}

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                aid = int(row["id"])
                if aid in phase4a_ids:
                    status = row["impl_status"].strip()
                    assert status == "EXISTING_PARTIAL", (
                        f"Rule {aid} expected EXISTING_PARTIAL after Phase 4A, got {status}"
                    )

    def test_phase4a_adapters_registered(self):
        """All 8 Phase 4A rules have adapters in the harness."""
        from audit_rules.adapters import CompatibilityHarness
        from audit_rules.registry import load_registry

        checklist = PROJECT_ROOT / "audit_specs" / "technical_seo_master_checklist_80.csv"
        mapping = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        if not checklist.exists() or not mapping.exists():
            pytest.skip("Real CSV files not found")

        registry = load_registry(str(checklist), str(mapping))
        harness = CompatibilityHarness(registry)

        expected_rule_ids = {
            "tag_archive_search_indexability",
            "media_sitemap",
            "xmlrpc_rest_api_exposure",
            "sitemap_lastmod_accuracy",
            "crawlable_a_href_links",
            "internal_links_to_redirects",
            "multilingual_canonical",
            "staging_site_indexed",
        }
        registered = set(harness._adapters.keys())
        missing = expected_rule_ids - registered
        assert not missing, f"Phase 4A rule_ids not in harness: {missing}"
        assert expected_rule_ids.issubset(registered)

    def test_adapter_count_61(self):
        """Total: 18 P1 + 13 P2 + 8 P3 + 8 P4A + 1 P4B = 48."""
        from audit_rules.adapters import CompatibilityHarness
        from audit_rules.registry import load_registry

        checklist = PROJECT_ROOT / "audit_specs" / "technical_seo_master_checklist_80.csv"
        mapping = PROJECT_ROOT / "audit_specs" / "master_audit_mapping.csv"
        if not checklist.exists() or not mapping.exists():
            pytest.skip("Real CSV files not found")

        registry = load_registry(str(checklist), str(mapping))
        harness = CompatibilityHarness(registry)
        assert len(harness._adapters) == 61, (
            f"Expected 61 adapters, got {len(harness._adapters)}"
        )
