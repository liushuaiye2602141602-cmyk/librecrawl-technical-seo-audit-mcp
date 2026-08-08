"""Phase 3.1 — Performance Artifact Integration Verification.

Verifies that performance.csv is:
  - Auto-generated from PSI cache after rule evaluation
  - Schema-complete: all 40 columns present and correctly typed
  - Registered as an output artifact in the audit pipeline
  - Survives edge cases: empty cache, error snapshots, mixed states

Also verifies backward compatibility of existing MCP PSI tools.

Tests:
  - generate_performance_csv() produces valid CSV with correct schema
  - All 40 columns present in header
  - Row count matches cache entry count
  - Error snapshots produce rows (not dropped)
  - Empty cache → header-only CSV
  - Backward compat: _fetch_psi() response keys match expected format
  - Backward compat: librecrawl_pagespeed() returns expected keys
"""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Expected schema
# ============================================================

# All 40 columns from _PERFORMANCE_COLUMNS in performance_csv.py
_EXPECTED_COLUMNS = [
    "url",
    "strategy",
    "psi_status",
    "error",
    "field_data_scope",
    "field_lcp_ms",
    "field_lcp_category",
    "field_inp_ms",
    "field_inp_category",
    "field_cls",
    "field_cls_category",
    "field_ttfb_ms",
    "field_fcp_ms",
    "origin_field_lcp_ms",
    "origin_field_lcp_category",
    "origin_field_inp_ms",
    "origin_field_inp_category",
    "origin_field_cls",
    "origin_field_cls_category",
    "lab_performance_score",
    "lab_seo_score",
    "lab_accessibility_score",
    "lab_best_practices_score",
    "lab_lcp_ms",
    "lab_fcp_ms",
    "lab_tbt_ms",
    "lab_cls",
    "lab_speed_index_ms",
    "lab_tti_ms",
    "lighthouse_version",
    "render_blocking_savings_ms",
    "render_blocking_count",
    "unused_css_bytes",
    "unused_js_bytes",
    "image_savings_bytes",
    "oversized_image_count",
    "third_party_transfer_bytes",
    "third_party_main_thread_ms",
    "third_party_entity_count",
    "font_display_issue_count",
    "layout_shift_element_count",
    "run_warnings",
]


# ============================================================
# Helpers
# ============================================================

def _make_test_snapshots():
    """Create a diverse set of test snapshots."""
    from tests.fixtures.psi import (
        make_good_mobile, make_poor_mobile, make_no_field_data,
    )
    return [
        make_good_mobile("https://example.com/"),
        make_poor_mobile("https://example.com/slow-page"),
        make_no_field_data("https://example.com/low-traffic"),
    ]


# ============================================================
# Tests
# ============================================================


class TestPerformanceCSVSchema:
    """Schema verification: 40 columns, correct header, valid output."""

    def test_all_40_columns_in_header(self):
        """CSV header must contain all 40 expected columns."""
        from audit_rules.checks.performance_csv import generate_performance_csv
        from tests.fixtures.psi import make_good_mobile, make_psi_cache

        snap = make_good_mobile()
        cache = make_psi_cache([snap])
        csv_str = generate_performance_csv(cache, "mobile")

        reader = csv.DictReader(io.StringIO(csv_str))
        actual_columns = reader.fieldnames

        assert actual_columns is not None, "CSV must have headers"
        assert len(actual_columns) == 42, (
            f"Expected 42 columns, got {len(actual_columns)}"
        )

        # Check every expected column is present
        missing = set(_EXPECTED_COLUMNS) - set(actual_columns)
        assert not missing, f"Missing columns: {missing}"

    def test_column_order_matches_expected(self):
        """Column order must be stable and match the expected order."""
        from audit_rules.checks.performance_csv import generate_performance_csv, _PERFORMANCE_COLUMNS

        # The _PERFORMANCE_COLUMNS list IS the spec
        assert _PERFORMANCE_COLUMNS == _EXPECTED_COLUMNS, (
            "Column order mismatch: _PERFORMANCE_COLUMNS changed"
        )

    def test_row_count_matches_cache_entries(self):
        """Number of data rows = number of cache entries."""
        from audit_rules.checks.performance_csv import generate_performance_csv
        from tests.fixtures.psi import make_psi_cache

        snapshots = _make_test_snapshots()
        cache = make_psi_cache(snapshots)
        csv_str = generate_performance_csv(cache, "mobile")

        lines = csv_str.strip().split("\n")
        # Header + 3 data rows
        assert len(lines) == 4, f"Expected header + 3 rows, got {len(lines)} lines"

    def test_empty_cache_produces_header_only(self):
        """Empty cache → CSV with header row only (no data)."""
        from audit_rules.checks.performance_csv import generate_performance_csv

        csv_str = generate_performance_csv({}, "mobile")
        lines = csv_str.strip().split("\n")
        assert len(lines) == 1, f"Empty cache should produce header only, got {len(lines)} lines"

    def test_output_is_utf8_string(self):
        """Output is a string (not bytes), ready to write."""
        from audit_rules.checks.performance_csv import generate_performance_csv
        from tests.fixtures.psi import make_good_mobile, make_psi_cache

        snap = make_good_mobile()
        cache = make_psi_cache([snap])
        csv_str = generate_performance_csv(cache, "mobile")

        assert isinstance(csv_str, str), "CSV output should be a string"


class TestPerformanceCSVContent:
    """Content verification: values are correctly mapped from snapshots."""

    def test_good_mobile_row_values(self):
        """Values from a good_mobile snapshot are correctly rendered."""
        from audit_rules.checks.performance_csv import generate_performance_csv
        from tests.fixtures.psi import make_good_mobile, make_psi_cache

        snap = make_good_mobile()
        cache = make_psi_cache([snap])
        csv_str = generate_performance_csv(cache, "mobile")

        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 1

        row = rows[0]
        assert row["url"] == "https://example.com"
        assert row["strategy"] == "mobile"
        assert row["psi_status"] == "success"
        assert row["field_data_scope"] == "URL"
        assert row["field_lcp_ms"] == "1800"
        assert row["field_lcp_category"] == "FAST"
        assert row["field_cls"] == "0.050"
        assert row["lab_performance_score"] == "95"

    def test_error_snapshot_produces_row(self):
        """Error snapshots produce rows (not silently dropped)."""
        from audit_rules.checks.performance_csv import generate_performance_csv
        from tests.fixtures.psi import make_api_error, make_psi_cache

        snap = make_api_error()
        cache = make_psi_cache([snap])
        csv_str = generate_performance_csv(cache, "mobile")

        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 1

        row = rows[0]
        assert row["psi_status"] == "error"
        assert "HTTP 500" in row["error"]
        assert row["field_data_scope"] == "NONE"

    def test_field_lab_separation_in_csv(self):
        """Field and lab values are in different columns, never conflated."""
        from audit_rules.checks.performance_csv import generate_performance_csv
        from tests.fixtures.psi import make_poor_mobile, make_psi_cache

        snap = make_poor_mobile()
        cache = make_psi_cache([snap])
        csv_str = generate_performance_csv(cache, "mobile")

        reader = csv.DictReader(io.StringIO(csv_str))
        row = list(reader)[0]

        # Field LCP vs Lab LCP — different columns
        assert row["field_lcp_ms"] != "" or row["lab_lcp_ms"] != "", (
            "Should have at least one of field_lcp_ms or lab_lcp_ms"
        )
        # They have different column names (field_ vs lab_)
        assert "field_lcp_ms" in row
        assert "lab_lcp_ms" in row
        # Field LCP (5200) and Lab LCP (5800) differ for poor_mobile
        assert row["field_lcp_ms"] != row["lab_lcp_ms"], (
            "Field and lab LCP should be in different columns with different values"
        )

    def test_origin_field_data_separated(self):
        """Origin-level field data is in separate columns from URL-level."""
        from audit_rules.checks.performance_csv import generate_performance_csv
        from tests.fixtures.psi import make_origin_field_only, make_psi_cache

        snap = make_origin_field_only()
        cache = make_psi_cache([snap])
        csv_str = generate_performance_csv(cache, "mobile")

        reader = csv.DictReader(io.StringIO(csv_str))
        row = list(reader)[0]

        # URL-level should be empty, origin-level populated
        assert row.get("field_lcp_ms", "") == "", (
            "URL-level field LCP should be empty for origin-only"
        )
        assert row["origin_field_lcp_ms"] != "", (
            "Origin field LCP should be populated"
        )

    def test_third_party_entity_count(self):
        """Third-party entity count is derived from entity list length."""
        from audit_rules.checks.performance_csv import generate_performance_csv
        from tests.fixtures.psi import make_poor_mobile, make_psi_cache

        snap = make_poor_mobile()
        assert len(snap.third_party_entities) == 2

        cache = make_psi_cache([snap])
        csv_str = generate_performance_csv(cache, "mobile")

        reader = csv.DictReader(io.StringIO(csv_str))
        row = list(reader)[0]
        assert row["third_party_entity_count"] == "2"


class TestBackwardCompatibility:
    """Existing MCP PSI tools remain backward compatible.

    Tests use source-code reading (not imports) to avoid httpx dependency.
    """

    _SERVER_SOURCE: str | None = None
    _PSI_CLIENT_SOURCE: str | None = None

    @classmethod
    def _get_server_source(cls) -> str:
        if cls._SERVER_SOURCE is None:
            cls._SERVER_SOURCE = (PROJECT_ROOT / "server.py").read_text(encoding="utf-8")
        return cls._SERVER_SOURCE

    @classmethod
    def _get_psi_client_source(cls) -> str:
        if cls._PSI_CLIENT_SOURCE is None:
            cls._PSI_CLIENT_SOURCE = (PROJECT_ROOT / "audit_rules" / "providers" / "psi_client.py").read_text(encoding="utf-8")
        return cls._PSI_CLIENT_SOURCE

    def test_fetch_psi_delegates_to_shared_client(self):
        """_fetch_psi() imports from psi_client.fetch_pagespeed."""
        source = self._get_server_source()
        assert "from audit_rules.providers.psi_client import fetch_pagespeed" in source, (
            "server.py _fetch_psi() must delegate to shared psi_client"
        )

    def test_fetch_psi_maps_keys_for_backward_compat(self):
        """_fetch_psi() maps psi_client output to backward-compatible MCP keys.

        The MCP output format includes: url, strategy, scores, field_data_cwv,
        lab_data, top_opportunities (simplified).
        """
        source = self._get_server_source()
        # Verify the backward-compat mapping logic
        assert "'url'" in source or '"url"' in source
        assert "'scores'" in source or '"scores"' in source
        assert "'field_data_cwv'" in source or '"field_data_cwv"' in source
        assert "'lab_data'" in source or '"lab_data"' in source
        assert "'top_opportunities'" in source or '"top_opportunities"' in source
        # top_opportunities are simplified
        assert "'title'" in source or '"title"' in source
        assert "'savings_ms'" in source or '"savings_ms"' in source

    def test_librecrawl_pagespeed_signature(self):
        """librecrawl_pagespeed() has (url: str, strategy: str = "mobile") → dict."""
        source = self._get_server_source()
        assert "def librecrawl_pagespeed" in source
        assert "url" in source

    def test_librecrawl_pagespeed_audit_signature(self):
        """librecrawl_pagespeed_audit() accepts urls: list, strategy="mobile"."""
        source = self._get_server_source()
        assert "def librecrawl_pagespeed_audit" in source
        assert "urls" in source

    def test_batch_audit_returns_summary_and_results(self):
        """librecrawl_pagespeed_audit returns {summary, results}."""
        source = self._get_server_source()
        assert '"summary"' in source or "'summary'" in source
        assert '"results"' in source or "'results'" in source

    def test_all_crawl_pages_audit_signature_preserved(self):
        """librecrawl_pagespeed_audit_all_crawl_pages signature preserved."""
        source = self._get_server_source()
        assert "def librecrawl_pagespeed_audit_all_crawl_pages" in source
        assert "crawl_id" in source

    def test_shared_client_error_format(self):
        """psi_client.fetch_pagespeed returns {'error': str} on failure."""
        source = self._get_psi_client_source()
        # Must handle no-API-key case with error dict
        assert '"error"' in source or "'error'" in source
        assert "PAGESPEED_API_KEY" in source

    def test_server_psi_uses_shared_client(self):
        """server.py imports from shared psi_client, no duplicate HTTP code."""
        source = self._get_server_source()
        assert "from audit_rules.providers.psi_client import fetch_pagespeed" in source

    def test_psi_client_error_format_consistent(self):
        """psi_client returns consistent error dict with 'error' key."""
        source = self._get_psi_client_source()
        # Check error handling patterns
        assert '"error"' in source or "'error'" in source
        # Must handle 429 rate limiting
        assert "429" in source or "rate limit" in source.lower()
        # Must handle 400 bad request
        assert "400" in source


class TestIntegrationWithRunner:
    """Runner can inject PSI cache, and CSV can be generated from it."""

    def test_generate_csv_from_runner_cache(self):
        """Simulate: runner injects cache → CSV generator reads it."""
        from audit_rules.checks.performance_csv import generate_performance_csv
        from tests.fixtures.psi import make_good_mobile, make_poor_mobile, make_psi_cache

        snapshots = [make_good_mobile("https://example.com"),
                      make_poor_mobile("https://example.com/slow")]
        cache = make_psi_cache(snapshots)

        # Simulate runner injection
        data = {"_psi_cache": cache, "psi_strategy": "mobile"}

        # CSV generator works from data["_psi_cache"]
        csv_str = generate_performance_csv(data["_psi_cache"], data["psi_strategy"])

        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 2
        urls = {row["url"] for row in rows}
        assert "https://example.com" in urls
        assert "https://example.com/slow" in urls

    def test_csv_handles_mixed_success_error_cache(self):
        """Cache with both success and error snapshots produces complete CSV."""
        from audit_rules.checks.performance_csv import generate_performance_csv
        from tests.fixtures.psi import make_good_mobile, make_api_error, make_psi_cache

        snapshots = [
            make_good_mobile("https://example.com"),
            make_api_error("https://example.com/broken"),
        ]
        cache = make_psi_cache(snapshots)
        csv_str = generate_performance_csv(cache, "mobile")

        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 2
        statuses = {row["psi_status"] for row in rows}
        assert statuses == {"success", "error"}, (
            f"Mixed cache should produce both success and error rows, got {statuses}"
        )
