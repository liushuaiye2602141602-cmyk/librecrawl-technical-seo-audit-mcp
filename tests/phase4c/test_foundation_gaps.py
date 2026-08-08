"""TDD tests for the seven previously unbound partial rules."""

from __future__ import annotations

import pytest

from audit_rules.context import PageContext, SiteContext


def _rule(audit_id: int):
    from audit_rules.registry import load_registry

    return next(rule for rule in load_registry() if rule.audit_id == audit_id)


def _page(url="https://example.com/", **values) -> PageContext:
    raw = {
        "url": url,
        "status_code": 200,
        "title": "A useful and unique page title",
        "meta_description": "Description",
        "h1": "Heading",
        "canonical_url": url,
        "robots": "index, follow",
        "word_count": 300,
    }
    raw.update(values)
    return PageContext.from_export(raw)


class TestRule2Sitemap:
    def test_missing_sitemap_is_error(self):
        from audit_rules.checks.foundation_gaps import check_xml_sitemap_valid

        findings = check_xml_sitemap_valid(
            _rule(2), SiteContext(base_url="https://example.com"), [], {}
        )

        assert len(findings) == 1
        assert findings[0].severity == "Error"

    def test_sitemap_broken_noindex_and_noncanonical_urls(self):
        from audit_rules.checks.foundation_gaps import check_xml_sitemap_valid

        urls = [
            "https://example.com/broken",
            "https://example.com/noindex",
            "https://example.com/canonicalized",
        ]
        site = SiteContext(
            base_url="https://example.com",
            sitemap_found=True,
            sitemap_url_count=3,
            _site_data={"sitemap": {"found": True, "urls": urls}},
        )
        pages = [
            _page(urls[0], status_code=404),
            _page(urls[1], robots="noindex"),
            _page(urls[2], canonical_url="https://example.com/other"),
        ]

        findings = check_xml_sitemap_valid(_rule(2), site, pages, {})

        assert {f.detected_value for f in findings} == {
            "Sitemap URL returns HTTP 404",
            "Sitemap URL is noindex",
            "Sitemap URL canonicalizes elsewhere",
        }

    def test_clean_sitemap_has_no_local_findings(self):
        from audit_rules.checks.foundation_gaps import check_xml_sitemap_valid

        url = "https://example.com/"
        site = SiteContext(
            base_url=url,
            sitemap_found=True,
            sitemap_url_count=1,
            _site_data={"sitemap": {"found": True, "urls": [url]}},
        )
        assert check_xml_sitemap_valid(_rule(2), site, [_page(url)], {}) == []


class TestRule5CrawlBudget:
    def test_detects_session_calendar_search_and_faceted_patterns(self):
        from audit_rules.checks.foundation_gaps import check_crawl_budget_waste

        pages = [
            _page("https://example.com/a?PHPSESSID=abcdef1234567890"),
            _page("https://example.com/calendar?year=2099&month=12"),
            _page("https://example.com/search?q=shoes"),
            _page("https://example.com/shop?color=red&size=xl&brand=x&sort=price"),
        ]

        findings = check_crawl_budget_waste(
            _rule(5), SiteContext(base_url="https://example.com"), pages, {}
        )

        evidence = " ".join(f.evidence for f in findings)
        assert "session_parameter" in evidence
        assert "future_calendar" in evidence
        assert "internal_search" in evidence
        assert "faceted_parameter_count" in evidence

    def test_clean_urls_do_not_trigger(self):
        from audit_rules.checks.foundation_gaps import check_crawl_budget_waste

        pages = [_page("https://example.com/"), _page("https://example.com/about")]
        assert check_crawl_budget_waste(
            _rule(5), SiteContext(base_url="https://example.com"), pages, {}
        ) == []


class TestRule13Titles:
    def test_detects_missing_duplicate_and_estimated_truncation(self):
        from audit_rules.checks.foundation_gaps import check_title_uniqueness

        duplicate = "Industrial Components and Manufacturing Services"
        pages = [
            _page("https://example.com/missing", title=""),
            _page("https://example.com/a", title=duplicate),
            _page("https://example.com/b", title=duplicate),
            _page("https://example.com/wide", title="W" * 80),
        ]

        findings = check_title_uniqueness(
            _rule(13), SiteContext(base_url="https://example.com"), pages, {}
        )

        detected = {f.detected_value for f in findings}
        assert "Missing title" in detected
        assert any(value.startswith("Duplicate title") for value in detected)
        assert any(value.startswith("Estimated title width") for value in detected)

    def test_unique_reasonable_titles_do_not_trigger(self):
        from audit_rules.checks.foundation_gaps import check_title_uniqueness

        pages = [
            _page("https://example.com/a", title="Precision Components for Aerospace Teams"),
            _page("https://example.com/b", title="Custom Manufacturing for Medical Devices"),
        ]
        assert check_title_uniqueness(
            _rule(13), SiteContext(base_url="https://example.com"), pages, {}
        ) == []


class TestRule23CacheHeaders:
    def test_missing_exported_headers_is_not_executed(self):
        from audit_rules.adapters import DataUnavailableError
        from audit_rules.checks.foundation_gaps import check_cache_cdn

        with pytest.raises(DataUnavailableError, match="Response headers"):
            check_cache_cdn(
                _rule(23), SiteContext(base_url="https://example.com"), [_page()], {}
            )

    def test_missing_cache_policy_is_warning(self):
        from audit_rules.checks.foundation_gaps import check_cache_cdn

        page = _page(response_headers={"Content-Type": "text/html"})
        findings = check_cache_cdn(
            _rule(23), SiteContext(base_url="https://example.com"), [page], {}
        )

        assert any("cache-control" in f.evidence for f in findings)

    def test_cache_hit_headers_are_clean_case_insensitively(self):
        from audit_rules.checks.foundation_gaps import check_cache_cdn

        page = _page(response_headers={
            "CACHE-CONTROL": "public, max-age=3600",
            "Age": "120",
            "CF-Cache-Status": "HIT",
        })
        assert check_cache_cdn(
            _rule(23), SiteContext(base_url="https://example.com"), [page], {}
        ) == []


class TestRule25Https:
    def test_detects_http_coverage_mixed_content_and_bad_tls(self):
        from audit_rules.checks.foundation_gaps import check_https_certificate

        site = SiteContext(
            base_url="http://example.com",
            https_redirects=False,
            _site_data={"tls_certificate": {"valid": False, "days_remaining": -1}},
        )
        page = _page(
            "https://example.com/",
            body_html='<img src="http://cdn.example.com/image.jpg">',
        )

        findings = check_https_certificate(_rule(25), site, [page], {})
        evidence = " ".join(f.evidence for f in findings)
        assert "https_redirects=False" in evidence
        assert "mixed_content" in evidence
        assert "tls_valid=False" in evidence

    def test_clean_https_with_tls_evidence_has_no_findings(self):
        from audit_rules.checks.foundation_gaps import check_https_certificate

        site = SiteContext(
            base_url="https://example.com",
            https_redirects=True,
            _site_data={"tls_certificate": {"valid": True, "days_remaining": 90}},
        )
        assert check_https_certificate(_rule(25), site, [_page()], {}) == []

    def test_http_page_is_reported_even_when_site_redirect_probe_passed(self):
        from audit_rules.checks.foundation_gaps import check_https_certificate

        site = SiteContext(
            base_url="https://example.com",
            https_redirects=True,
            _site_data={"tls_certificate": {"valid": True, "days_remaining": 90}},
        )
        findings = check_https_certificate(
            _rule(25), site, [_page("http://example.com/legacy")], {}
        )

        assert any("page_scheme=http" in finding.evidence for finding in findings)


class TestRule66WordPressCacheSynergy:
    def test_dynamic_wordpress_page_cached_publicly_is_error(self):
        from audit_rules.checks.foundation_gaps import check_cache_plugin_cdn_synergy

        page = _page(
            "https://example.com/cart/",
            response_headers={
                "Cache-Control": "public, max-age=3600",
                "CF-Cache-Status": "HIT",
            },
        )
        findings = check_cache_plugin_cdn_synergy(
            _rule(66),
            SiteContext(base_url="https://example.com", site_profile="wordpress"),
            [page],
            {},
        )

        assert len(findings) == 1
        assert findings[0].severity == "Error"

    def test_dynamic_pages_bypass_and_anonymous_page_hits(self):
        from audit_rules.checks.foundation_gaps import check_cache_plugin_cdn_synergy

        pages = [
            _page("https://example.com/cart/", response_headers={
                "Cache-Control": "private, no-store", "CF-Cache-Status": "BYPASS"
            }),
            _page("https://example.com/", response_headers={
                "Cache-Control": "public, max-age=3600", "CF-Cache-Status": "HIT"
            }),
        ]
        assert check_cache_plugin_cdn_synergy(
            _rule(66),
            SiteContext(base_url="https://example.com", site_profile="wordpress"),
            pages,
            {},
        ) == []


def test_all_seven_previously_unbound_rules_are_registered():
    from audit_rules.adapters import CompatibilityHarness
    from audit_rules.registry import load_registry

    registry = load_registry()
    harness = CompatibilityHarness(registry)
    rule_ids = {
        rule.rule_id for rule in registry if rule.audit_id in {2, 5, 13, 23, 25, 40, 66}
    }

    assert rule_ids <= set(harness._adapters)
    assert len(harness._adapters) == 55


def test_missing_header_and_tls_sources_are_unknown_not_pass():
    from audit_rules.categories import ExecutionStatus, ResultStatus
    from audit_rules.registry import load_registry
    from audit_rules.runner import RuleRunner

    export = {
        "site_check": {"https_redirect": {"redirects": True}},
        "pages": [{
            "url": "https://example.com/", "status_code": 200,
            "title": "A valid unique page title", "robots": "index, follow",
        }],
        "links": [],
    }
    _, rows = RuleRunner(load_registry()).run_from_export(export, "https://example.com")

    for audit_id, source in [(23, "ResponseHeaders"), (25, "TLSCertificate")]:
        row = next(row for row in rows if row.audit_id == audit_id)
        assert row.execution_status == ExecutionStatus.NOT_CHECKED
        assert row.result_status == ResultStatus.UNKNOWN
        assert source in row.not_checked_reason


def test_partial_response_header_export_is_executed_partial():
    from audit_rules.categories import ExecutionStatus
    from audit_rules.registry import load_registry
    from audit_rules.runner import RuleRunner

    export = {
        "site_check": {},
        "pages": [
            {
                "url": "https://example.com/", "status_code": 200,
                "title": "Home", "response_headers": {"content-type": "text/html"},
            },
            {
                "url": "https://example.com/about", "status_code": 200,
                "title": "About",
            },
        ],
        "links": [],
    }
    _, rows = RuleRunner(load_registry()).run_from_export(export, "https://example.com")
    rule23 = next(row for row in rows if row.audit_id == 23)

    assert rule23.execution_status == ExecutionStatus.EXECUTED_PARTIAL
    assert "1/2" in rule23.not_checked_reason
