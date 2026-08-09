"""Phase 3.1 — Performance Sampling Determinism Verification.

Verifies that select_performance_sample() is deterministic:
  - Same input → same sample (order + selection) across 10 runs
  - Covers all 11 bucket categories when pages available
  - Respects the sample_limit parameter
  - Only selects 200-status pages
  - Returns consistent sampling_reason strings

Template-aware sampling covers 11 bucket categories:
  homepage, category_archive, product_service, solution_industry,
  blog_article, contact_about, high_internal_links, deep_page,
  large_page, language_dir, other
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Helpers — build PageContext lists for each bucket pattern
# ============================================================

def _ctx(url: str, **kwargs) -> object:
    """Quick PageContext builder."""
    from audit_rules.context import PageContext
    defaults = {
        "url": url,
        "status_code": 200,
        "depth": 1,
        "internal_links_count": 10,
        "word_count": 1000,
    }
    defaults.update(kwargs)
    return PageContext(**defaults)


# ============================================================
# Tests
# ============================================================


class TestSamplingDeterminism:
    """Same input → same output, 10 runs."""

    def test_deterministic_selection_10_runs(self):
        """Repeated calls with same input produce identical results."""
        from audit_rules.providers.pagespeed_provider import select_performance_sample

        pages = [
            _ctx("https://example.com/"),
            _ctx("https://example.com/category/seo/"),
            _ctx("https://example.com/product/widget-1/"),
            _ctx("https://example.com/blog/10-seo-tips/"),
            _ctx("https://example.com/about/"),
            _ctx("https://example.com/contact/"),
            _ctx("https://example.com/services/consulting/"),
            _ctx("https://example.com/solutions/enterprise/"),
            _ctx("https://example.com/deep/page/1/subpage/a"),
            _ctx("https://example.com/high-links-page/", internal_links_count=50),
        ]

        first_run = select_performance_sample(pages, limit=10)
        first_urls = [ctx.url for ctx, reason in first_run]
        first_reasons = [reason for ctx, reason in first_run]

        for i in range(10):
            run = select_performance_sample(pages, limit=10)
            run_urls = [ctx.url for ctx, reason in run]
            run_reasons = [reason for ctx, reason in run]
            assert run_urls == first_urls, (
                f"Run {i}: URL order differs from first run"
            )
            assert run_reasons == first_reasons, (
                f"Run {i}: Reason order differs from first run"
            )

    def test_deterministic_with_limit(self):
        """Deterministic even when limit < total pages."""
        from audit_rules.providers.pagespeed_provider import select_performance_sample

        pages = [
            _ctx(f"https://example.com/page-{i}/") for i in range(20)
        ]

        first_run = select_performance_sample(pages, limit=5)
        first_urls = [ctx.url for ctx, reason in first_run]

        for _ in range(10):
            run = select_performance_sample(pages, limit=5)
            run_urls = [ctx.url for ctx, reason in run]
            assert run_urls == first_urls, "Selection should be deterministic"

    def test_deterministic_when_all_in_other_bucket(self):
        """Even when all pages land in 'other', order is deterministic."""
        from audit_rules.providers.pagespeed_provider import select_performance_sample

        # Use internal_links_count=0 and low word_count to avoid
        # high_internal_links and large_page catching these first
        pages = [
            _ctx(f"https://example.com/misc/random-{i:03d}/",
                 internal_links_count=0, word_count=1) for i in range(30)
        ]

        first_run = select_performance_sample(pages, limit=10)
        first_urls = [ctx.url for ctx, reason in first_run]

        for _ in range(10):
            run = select_performance_sample(pages, limit=10)
            run_urls = [ctx.url for ctx, reason in run]
            assert run_urls == first_urls, (
                "Even 'other' bucket should be deterministic (sorted by URL)"
            )


class TestSamplingCoverage:
    """Sampling covers all 11 bucket categories."""

    def test_homepage_detected(self):
        """Homepage is identified and sampled."""
        from audit_rules.providers.pagespeed_provider import select_performance_sample

        pages = [_ctx("https://example.com/")]
        result = select_performance_sample(pages, limit=10)
        assert len(result) == 1
        page_ctx, reason = result[0]
        assert "example.com" in page_ctx.url
        assert reason == "homepage"

    def test_category_archive_detected(self):
        """Category/archive URLs are bucketed correctly."""
        from audit_rules.providers.pagespeed_provider import select_performance_sample

        pages = [_ctx("https://example.com/category/seo/")]
        result = select_performance_sample(pages, limit=10)
        assert len(result) == 1
        _, reason = result[0]
        assert reason == "category_archive"

    def test_product_service_detected(self):
        """Product/service URLs are bucketed correctly."""
        from audit_rules.providers.pagespeed_provider import select_performance_sample

        pages = [
            _ctx("https://example.com/product/widget/"),
            _ctx("https://example.com/service/consulting/"),
        ]
        result = select_performance_sample(pages, limit=10)
        assert len(result) == 2
        reasons = {reason for _, reason in result}
        assert "product_service" in reasons

    def test_blog_article_detected(self):
        """Blog/article URLs are identified."""
        from audit_rules.providers.pagespeed_provider import select_performance_sample

        pages = [_ctx("https://example.com/blog/my-post/")]
        result = select_performance_sample(pages, limit=10)
        _, reason = result[0]
        assert reason == "blog_article"

    def test_contact_about_detected(self):
        """Contact/About URLs are identified."""
        from audit_rules.providers.pagespeed_provider import select_performance_sample

        pages = [
            _ctx("https://example.com/about/"),
            _ctx("https://example.com/contact/"),
        ]
        result = select_performance_sample(pages, limit=10)
        reasons = {reason for _, reason in result}
        assert "contact_about" in reasons

    def test_deep_page_detected(self):
        """Deep pages (depth ≥ 4) are identified."""
        from audit_rules.providers.pagespeed_provider import select_performance_sample

        pages = [_ctx("https://example.com/a/b/c/d/e/", depth=5)]
        result = select_performance_sample(pages, limit=10)
        _, reason = result[0]
        assert reason == "deep_page"

    def test_high_internal_links_detected(self):
        """Pages with high internal links are identified."""
        from audit_rules.providers.pagespeed_provider import select_performance_sample

        # Many pages → 75th percentile is above 10
        many_normal = [_ctx(f"https://example.com/other/{i}/", internal_links_count=5)
                       for i in range(10)]
        high_link = _ctx("https://example.com/high-link/", internal_links_count=500)
        pages = many_normal + [high_link]

        result = select_performance_sample(pages, limit=20)
        reasons = {reason for _, reason in result}
        assert "high_internal_links" in reasons

    def test_large_page_detected(self):
        """Large pages (high word count, ≥75th percentile) are identified.

        Uses helpers with moderate word count to push 75th percentile above
        the small pages' word_count so only the true outlier lands in large_page.
        """
        from audit_rules.providers.pagespeed_provider import select_performance_sample

        # Helpers push word_75th up (5000×10), outlier is even higher (50000)
        helpers = [_ctx(f"https://example.com/other/{i}/", word_count=5000,
                        internal_links_count=0)
                   for i in range(10)]
        outlier = _ctx("https://example.com/large-page/", word_count=50000,
                       internal_links_count=0)
        pages = helpers + [outlier]

        result = select_performance_sample(pages, limit=20)
        reasons = {reason for _, reason in result}
        assert "large_page" in reasons

    def test_language_dir_detected(self):
        """Language directories (/en/, /fr/, etc.) are identified."""
        from audit_rules.providers.pagespeed_provider import select_performance_sample

        pages = [
            _ctx("https://example.com/en/page/"),
            _ctx("https://example.com/en/about/"),
        ]
        result = select_performance_sample(pages, limit=10)
        _, reason = result[0]
        assert reason == "language_dir"

    def test_other_bucket_fallback(self):
        """Pages that don't match any bucket go to 'other'.

        Pages are classified in priority order. To reach 'other', a page must
        not trigger homepage, language_dir, category/archive, product/service,
        blog/article, contact/about, deep (depth≥4), high_internal_links
        (≥75th percentile), or large_page (≥75th percentile of word_count).

        We use high-percentile helper pages so the target falls below both
        link and word count 75th percentiles.
        """
        from audit_rules.providers.pagespeed_provider import select_performance_sample

        # Helpers with high values to push 75th percentiles up
        helpers = [_ctx(f"https://example.com/helper-{i}/",
                        word_count=5000, internal_links_count=50)
                   for i in range(10)]
        target = _ctx("https://example.com/misc/random-thing/",
                      word_count=100, internal_links_count=1)
        pages = helpers + [target]

        result = select_performance_sample(pages, limit=20)
        _, reason = result[0]  # First picked from each non-empty bucket — helpers are "other" too, but target may be first
        # At minimum, "other" is among the reasons
        reasons = {reason for _, reason in result}
        assert "other" in reasons

    def test_all_10_buckets_when_pages_available(self):
        """When all 10 reachable bucket categories have pages, all are represented.

        Note: 'solution_industry' is defined in the bucket dict but the current
        provider code has no dedicated detector — /solution/ and /solutions/
        patterns route to 'product_service'. This test covers the 10 buckets
        that are actually reachable.
        """
        from audit_rules.providers.pagespeed_provider import select_performance_sample

        pages = [
            _ctx("https://example.com/"),  # homepage
            _ctx("https://example.com/category/tech/"),  # category_archive
            _ctx("https://example.com/product/item-1/"),  # product_service
            _ctx("https://example.com/blog/post-1/"),  # blog_article
            _ctx("https://example.com/about/"),  # contact_about
            _ctx("https://example.com/high-link/", internal_links_count=500,
                 depth=1, word_count=100),  # high_internal_links
            _ctx("https://example.com/a/b/c/d/e/", depth=5,
                 internal_links_count=1, word_count=10),  # deep_page
            _ctx("https://example.com/large/", word_count=50000,
                 internal_links_count=1, depth=1),  # large_page
            _ctx("https://example.com/fr/bienvenue/", internal_links_count=1,
                 word_count=500),  # language_dir
            _ctx("https://example.com/misc/other-page/", internal_links_count=1,
                 word_count=100),  # other (low enough to stay below percentiles)
        ]

        result = select_performance_sample(pages, limit=10)
        reasons = {reason for _, reason in result}
        assert len(result) == 10, f"All 10 pages should be sampled, got {len(result)}"
        expected_buckets = {
            "homepage", "category_archive", "product_service",
            "blog_article", "contact_about",
            "high_internal_links", "deep_page", "large_page",
            "language_dir", "other",
        }
        assert reasons == expected_buckets, (
            f"Expected all 10 reachable buckets, missing: {expected_buckets - reasons}"
        )


class TestSamplingEdgeCases:
    """Edge cases: empty, non-200, limit constraints."""

    def test_empty_pages_returns_empty(self):
        """Empty page list → empty result."""
        from audit_rules.providers.pagespeed_provider import select_performance_sample
        result = select_performance_sample([], limit=10)
        assert result == []

    def test_no_200_pages_returns_empty(self):
        """All non-200 pages → empty result."""
        from audit_rules.providers.pagespeed_provider import select_performance_sample
        pages = [_ctx("https://example.com/404/", status_code=404),
                  _ctx("https://example.com/500/", status_code=500)]
        result = select_performance_sample(pages, limit=10)
        assert result == []

    def test_limit_zero_returns_empty(self):
        """limit=0 → empty result."""
        from audit_rules.providers.pagespeed_provider import select_performance_sample
        pages = [_ctx("https://example.com/")]
        result = select_performance_sample(pages, limit=0)
        assert result == []

    def test_limit_exceeds_pages_returns_all(self):
        """When limit > page count, returns all available pages."""
        from audit_rules.providers.pagespeed_provider import select_performance_sample
        pages = [
            _ctx("https://example.com/"),
            _ctx("https://example.com/about/"),
            _ctx("https://example.com/contact/"),
        ]
        result = select_performance_sample(pages, limit=100)
        assert len(result) == 3

    def test_only_200_pages_selected(self):
        """Non-200 status codes are excluded from sampling."""
        from audit_rules.providers.pagespeed_provider import select_performance_sample
        pages = [
            _ctx("https://example.com/", status_code=200),
            _ctx("https://example.com/404/", status_code=404),
            _ctx("https://example.com/500/", status_code=500),
            _ctx("https://example.com/about/", status_code=200),
        ]
        result = select_performance_sample(pages, limit=10)
        urls = {ctx.url for ctx, reason in result}
        assert "https://example.com/404/" not in urls
        assert "https://example.com/500/" not in urls
        assert "https://example.com/" in urls
        assert "https://example.com/about/" in urls

    def test_result_type_is_tuple_of_pagecontext_and_str(self):
        """Each result item is (PageContext, str)."""
        from audit_rules.providers.pagespeed_provider import select_performance_sample
        from audit_rules.context import PageContext
        pages = [_ctx("https://example.com/")]
        result = select_performance_sample(pages, limit=10)
        assert len(result) == 1
        assert isinstance(result[0], tuple)
        assert isinstance(result[0][0], PageContext)
        assert isinstance(result[0][1], str)
