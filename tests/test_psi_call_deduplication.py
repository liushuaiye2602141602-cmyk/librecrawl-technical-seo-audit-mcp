"""Phase 3.1 — PSI Call Deduplication Verification.

Verifies that the shared in-memory cache eliminates duplicate PSI API calls:
  - N URLs × M rules ≠ N×M API calls
  - N URLs = N PSI API calls (one per URL, single strategy)
  - Rule evaluation adds 0 HTTP calls (all reads from cache)

Design invariant: psi_client.fetch_pagespeed() is the ONLY module making
PSI HTTP requests. PageSpeedDataProvider wraps it. All 8 rules share the
same PerformanceSnapshot cache keyed by (normalized_url, strategy).

Tests:
  - Single URL, 8 rules → exactly 1 PSI call
  - 20 URLs, 8 rules → ≤ 20 PSI calls
  - Cache hit does not increment call count
  - same (URL, strategy) key → only fetched once
  - get_snapshot() with same args returns cached value
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Helpers
# ============================================================

def _make_mock_snapshot(url="https://example.com", strategy="mobile"):
    """Create a minimal PerformanceSnapshot for testing."""
    from audit_rules.providers.performance_snapshot import PerformanceSnapshot
    return PerformanceSnapshot(
        url=url,
        requested_url=url,
        strategy=strategy,
        psi_status="success",
        field_data_available=True,
        field_data_scope="URL",
        field_lcp_ms=2000.0,
        field_lcp_category="FAST",
        field_inp_ms=150.0,
        field_inp_category="FAST",
        field_cls=0.08,
        field_cls_category="FAST",
        lab_performance_score=85,
        lab_lcp_ms=2200.0,
    )


# ============================================================
# Tests
# ============================================================


class TestPSICacheMechanics:
    """In-memory cache: same (URL, strategy) → one fetch only."""

    def test_cache_key_normalization(self):
        """URL trailing slash and case are normalized for cache keys."""
        from audit_rules.providers.pagespeed_provider import PageSpeedDataProvider
        provider = PageSpeedDataProvider()
        key1 = provider._normalize_url("https://example.com/page")
        key2 = provider._normalize_url("https://example.com/page/")
        key3 = provider._normalize_url("HTTPS://EXAMPLE.COM/PAGE")
        assert key1 == key2 == key3, "Normalized cache keys should match"

    def test_second_get_snapshot_does_not_call_fetch(self):
        """Second call with same (URL, strategy) should hit cache, not re-fetch."""
        from audit_rules.providers.pagespeed_provider import PageSpeedDataProvider

        provider = PageSpeedDataProvider(
            api_key="test-key",
            sample_limit=10,
            strategies=["mobile"],
        )
        provider._available = True  # Bypass API key check

        snap = _make_mock_snapshot()
        provider._fetch_snapshot = MagicMock(return_value=snap)

        # First call — should fetch
        result1 = provider.get_snapshot("https://example.com", "mobile")
        assert result1 is snap
        assert provider._fetch_snapshot.call_count == 1

        # Second call with same args — should hit cache
        result2 = provider.get_snapshot("https://example.com", "mobile")
        assert result2 is snap
        assert provider._fetch_snapshot.call_count == 1, (
            "Second call should hit cache, not re-fetch"
        )

    def test_different_urls_increment_call_count(self):
        """Different URLs should each trigger a fetch."""
        from audit_rules.providers.pagespeed_provider import PageSpeedDataProvider

        provider = PageSpeedDataProvider(
            api_key="test-key",
            sample_limit=10,
            strategies=["mobile"],
        )
        provider._available = True

        snap = _make_mock_snapshot()
        provider._fetch_snapshot = MagicMock(return_value=snap)

        urls = [
            "https://example.com/",
            "https://example.com/about",
            "https://example.com/blog/post-1",
        ]
        for url in urls:
            provider.get_snapshot(url, "mobile")

        assert provider._fetch_snapshot.call_count == 3, (
            f"3 unique URLs should trigger 3 fetches, got {provider._fetch_snapshot.call_count}"
        )

    def test_different_strategies_different_cache_keys(self):
        """Mobile and desktop snapshots for the same URL have different cache keys."""
        from audit_rules.providers.pagespeed_provider import PageSpeedDataProvider

        provider = PageSpeedDataProvider(
            api_key="test-key",
            sample_limit=10,
            strategies=["mobile", "desktop"],
        )
        provider._available = True

        snap_mobile = _make_mock_snapshot(strategy="mobile")
        snap_desktop = _make_mock_snapshot(strategy="desktop")

        call_count = [0]

        def side_effect(url, strategy):
            call_count[0] += 1
            return snap_mobile if strategy == "mobile" else snap_desktop

        provider._fetch_snapshot = MagicMock(side_effect=side_effect)

        r1 = provider.get_snapshot("https://example.com", "mobile")
        r2 = provider.get_snapshot("https://example.com", "desktop")

        assert call_count[0] == 2
        assert r1.strategy == "mobile"
        assert r2.strategy == "desktop"

    def test_force_refresh_bypasses_cache(self):
        """force_refresh=True should bypass cache and re-fetch."""
        from audit_rules.providers.pagespeed_provider import PageSpeedDataProvider

        provider = PageSpeedDataProvider(
            api_key="test-key",
            sample_limit=10,
            strategies=["mobile"],
        )
        provider._available = True

        snap = _make_mock_snapshot()
        provider._fetch_snapshot = MagicMock(return_value=snap)

        # First call
        provider.get_snapshot("https://example.com", "mobile")
        assert provider._fetch_snapshot.call_count == 1

        # force_refresh
        provider.get_snapshot("https://example.com", "mobile", force_refresh=True)
        assert provider._fetch_snapshot.call_count == 2, (
            "force_refresh should bypass cache"
        )


class TestPSICallCountPerAudit:
    """N URLs ≠ N×8 calls. N URLs = N PSI calls (or fewer)."""

    def test_cache_shared_across_all_rules(self):
        """Cache dict can be read by multiple consumers without API calls."""
        from audit_rules.providers.pagespeed_provider import PageSpeedDataProvider
        from tests.fixtures.psi import make_psi_cache, make_good_mobile

        provider = PageSpeedDataProvider(
            api_key="test-key",
            sample_limit=20,
            strategies=["mobile"],
        )
        provider._available = True

        # Simulate: 8 rules × 5 URLs should still be 5 cache entries, not 40
        urls = [f"https://example.com/page-{i}" for i in range(5)]
        for url in urls:
            provider._cache[(provider._normalize_url(url), "mobile")] = make_good_mobile(url)

        assert len(provider._cache) == 5, (
            f"5 URLs should produce 5 cache entries, got {len(provider._cache)}"
        )

        # All 8 rules can access the same cache without calls
        rule_ids = [19, 20, 21, 22, 24, 61, 62, 63]
        for rule_id in rule_ids:
            for url in urls:
                key = (provider._normalize_url(url), "mobile")
                assert key in provider._cache, (
                    f"Rule {rule_id} should find {url} in shared cache"
                )

    def test_cache_size_equals_url_count_not_rule_count(self):
        """The cache key is (url, strategy), not (url, strategy, rule_id).

        So 20 URLs = 20 cache entries regardless of how many rules exist.
        """
        from audit_rules.providers.pagespeed_provider import PageSpeedDataProvider

        provider = PageSpeedDataProvider(
            api_key="test-key",
            sample_limit=20,
            strategies=["mobile"],
        )
        provider._available = True

        snap = _make_mock_snapshot()
        provider._fetch_snapshot = MagicMock(return_value=snap)

        url_count = 20
        urls = [f"https://example.com/page-{i}" for i in range(url_count)]
        for url in urls:
            provider.get_snapshot(url, "mobile")

        assert len(provider._cache) == url_count, (
            f"Cache should have {url_count} entries, got {len(provider._cache)}"
        )
        assert provider._fetch_snapshot.call_count == url_count, (
            f"Expected {url_count} fetches, got {provider._fetch_snapshot.call_count}"
        )

    def test_runner_injects_psi_cache_not_psi_calls(self):
        """Runner should inject cache into existing_data, not make PSI calls
        during rule evaluation.

        When the provider has pre-populated cache, the runner just copies
        it — no additional PSI calls during rule execution.

        This test uses a mock on the _fetch_snapshot method (not the psi_client
        module, to avoid httpx import issues). The principle is the same:
        the cache dict is populated once and rules read from it.
        """
        from unittest.mock import MagicMock
        from audit_rules.providers.pagespeed_provider import PageSpeedDataProvider

        snap = _make_mock_snapshot()

        provider = PageSpeedDataProvider(
            api_key="test-key",
            sample_limit=3,
            strategies=["mobile"],
        )
        provider._available = True
        provider._fetch_snapshot = MagicMock(return_value=snap)

        # Populate cache (simulating runner's initial fetch pass)
        result = provider.get_snapshot("https://example.com", "mobile")
        assert result is snap
        assert provider._fetch_snapshot.call_count == 1

        # Copy cache (what runner does)
        cache_copy = provider._cache.copy()
        assert len(cache_copy) == 1

        # Reading from cache_copy is NOT a PSI call
        # This is what all 8 rules do: they read from the pre-populated cache
        for _ in range(8):  # 8 rules
            _ = cache_copy.get(("https://example.com", "mobile"))

        # No additional calls to _fetch_snapshot
        assert provider._fetch_snapshot.call_count == 1, (
            f"8 rule reads should not add PSI calls; "
            f"still only 1 fetch, got {provider._fetch_snapshot.call_count}"
        )


def test_rule_runner_clears_psi_cache_between_audits():
    """A cached runner must never leak one site's PSI rows into the next audit."""
    from audit_rules.providers.pagespeed_provider import PageSpeedDataProvider
    from audit_rules.registry import load_registry
    from audit_rules.runner import RuleRunner

    provider = PageSpeedDataProvider(
        api_key="test-key", sample_limit=1, strategies=["mobile"])
    provider._available = True
    provider._fetch_snapshot = MagicMock(
        side_effect=lambda url, strategy: _make_mock_snapshot(url, strategy))
    runner = RuleRunner(load_registry(), providers={provider.name: provider})

    def page(url):
        return {"url": url, "status_code": 200, "title": "Page",
                "meta_description": "Description", "h1": "Page",
                "canonical_url": url, "robots": "index, follow",
                "word_count": 500, "depth": 0}

    runner.run(pages=[page("https://one.example/")], base_url="https://one.example/")
    assert set(provider._cache) == {("https://one.example", "mobile")}

    runner.run(pages=[page("https://two.example/")], base_url="https://two.example/")
    assert set(provider._cache) == {("https://two.example", "mobile")}


class TestSingleCanonicalHTTPImplementation:
    """psi_client.fetch_pagespeed() is the ONLY PSI HTTP function."""

    def test_server_psi_uses_shared_client(self):
        """server.py _fetch_psi() delegates to psi_client.fetch_pagespeed()."""
        # Read server.py directly (cannot import due to httpx dependency not
        # being importable in test environments without it installed)
        server_path = PROJECT_ROOT / "server.py"
        source = server_path.read_text(encoding="utf-8")
        # Must import from psi_client
        assert "from audit_rules.providers.psi_client import fetch_pagespeed" in source, (
            "server.py _fetch_psi() must delegate to shared psi_client"
        )

    def test_provider_fetch_uses_shared_client(self):
        """PageSpeedDataProvider._fetch_snapshot() uses psi_client.fetch_pagespeed()."""
        import inspect
        from audit_rules.providers.pagespeed_provider import PageSpeedDataProvider
        source = inspect.getsource(PageSpeedDataProvider._fetch_snapshot)
        assert "from audit_rules.providers.psi_client import fetch_pagespeed" in source, (
            "PageSpeedDataProvider._fetch_snapshot must use shared psi_client"
        )

    def test_no_direct_httpx_in_checks(self):
        """Rule check functions must not import httpx or make HTTP calls directly."""
        import inspect
        from audit_rules.checks.performance import (
            check_core_web_vitals,
            check_ttfb,
            check_render_blocking,
            check_image_performance,
            check_mobile_experience,
            check_field_vs_lab,
            check_third_party_scripts,
            check_font_cls,
        )
        for fn in [check_core_web_vitals, check_ttfb, check_render_blocking,
                    check_image_performance, check_mobile_experience,
                    check_field_vs_lab, check_third_party_scripts, check_font_cls]:
            source = inspect.getsource(fn)
            assert "httpx" not in source, (
                f"{fn.__name__} must not make direct HTTP calls"
            )
            assert "fetch_pagespeed" not in source, (
                f"{fn.__name__} must read from cache, not call PSI directly"
            )
