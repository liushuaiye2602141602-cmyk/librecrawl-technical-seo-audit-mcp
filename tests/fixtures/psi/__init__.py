"""PSI mock fixtures — 11 pre-built PerformanceSnapshot variants for TDD.

Each builder function returns a PerformanceSnapshot or a data dict suitable
for injection into the adapter `data` parameter.

Fixture variants:
  1. good_mobile        — CWV all GOOD, high scores, URL-level field data
  2. poor_mobile        — CWV all POOR, low scores, URL-level field data
  3. no_field_data      — No CrUX data, lab only with good lab score
  4. origin_field_only  — Origin-level field data only (no URL-level)
  5. partial_lighthouse — Missing some Lighthouse audits (no TBT, no CLS)
  6. api_error          — PSI API error (403/500/429)
  7. rate_limit         — Rate limit error
  8. redirected_url     — URL was redirected, final_url differs
  9. third_party_heavy  — Many third-party scripts with high main-thread time
  10. image_heavy       — Many image optimization opportunities
  11. cls_font_issue    — Font display issues and significant CLS
"""

from __future__ import annotations

from dataclasses import replace
from audit_rules.providers.performance_snapshot import (
    PerformanceSnapshot,
    RenderBlockingResource,
    ImageOpportunity,
    ThirdPartyEntity,
    FontIssue,
    LayoutShiftElement,
)
from audit_rules.context import PageContext, SiteContext


# ============================================================
# 1. good_mobile — all CWV GOOD, high scores
# ============================================================

def make_good_mobile(url: str = "https://example.com") -> PerformanceSnapshot:
    """All CWV GOOD at URL level, perf score 95."""
    return PerformanceSnapshot(
        url=url,
        requested_url=url,
        final_url=url,
        strategy="mobile",
        fetch_timestamp="2026-08-09T12:00:00Z",
        source="pagespeed_insights",
        # URL-level field data: all GOOD
        field_data_available=True,
        field_data_scope="URL",
        field_lcp_ms=1800.0,
        field_lcp_category="FAST",
        field_inp_ms=120.0,
        field_inp_category="FAST",
        field_cls=0.05,
        field_cls_category="FAST",
        field_fcp_ms=1200.0,
        field_fcp_category="FAST",
        field_ttfb_ms=350.0,
        field_ttfb_category="FAST",
        # Origin-level field data (same as URL for simplicity)
        origin_field_lcp_ms=2100.0,
        origin_field_lcp_category="FAST",
        origin_field_inp_ms=140.0,
        origin_field_inp_category="FAST",
        origin_field_cls=0.08,
        origin_field_cls_category="FAST",
        # Lab data: high scores
        lab_performance_score=95,
        lab_seo_score=100,
        lab_accessibility_score=98,
        lab_best_practices_score=100,
        lab_lcp_ms=1600.0,
        lab_fcp_ms=1100.0,
        lab_tbt_ms=80.0,
        lab_cls=0.03,
        lab_speed_index_ms=1800.0,
        lab_tti_ms=2000.0,
        lighthouse_version="12.0.0",
        # Minimal opportunities
        render_blocking_savings_ms=100,
        render_blocking_resources=[],
        unused_css_bytes=5000,
        unused_js_bytes=10000,
        image_savings_bytes=20000,
        image_opportunities=[],
        oversized_image_count=0,
        third_party_transfer_bytes=30000,
        third_party_main_thread_ms=50,
        third_party_entities=[],
        font_display_issues=[],
        layout_shift_elements=[],
        run_warnings=[],
        psi_status="success",
    )


# ============================================================
# 2. poor_mobile — all CWV POOR
# ============================================================

def make_poor_mobile(url: str = "https://example.com/slow-page") -> PerformanceSnapshot:
    """CWV all POOR at URL level, perf score 32."""
    return PerformanceSnapshot(
        url=url,
        requested_url=url,
        final_url=url,
        strategy="mobile",
        fetch_timestamp="2026-08-09T12:00:00Z",
        source="pagespeed_insights",
        # URL-level field data: all POOR
        field_data_available=True,
        field_data_scope="URL",
        field_lcp_ms=5200.0,
        field_lcp_category="SLOW",
        field_inp_ms=650.0,
        field_inp_category="SLOW",
        field_cls=0.45,
        field_cls_category="SLOW",
        field_fcp_ms=3800.0,
        field_fcp_category="SLOW",
        field_ttfb_ms=1200.0,
        field_ttfb_category="SLOW",
        # Origin-level
        origin_field_lcp_ms=4800.0,
        origin_field_lcp_category="SLOW",
        origin_field_inp_ms=550.0,
        origin_field_inp_category="SLOW",
        origin_field_cls=0.38,
        origin_field_cls_category="SLOW",
        # Lab data
        lab_performance_score=32,
        lab_seo_score=85,
        lab_accessibility_score=72,
        lab_best_practices_score=67,
        lab_lcp_ms=5800.0,
        lab_fcp_ms=4000.0,
        lab_tbt_ms=1800.0,
        lab_cls=0.40,
        lab_speed_index_ms=6500.0,
        lab_tti_ms=8000.0,
        lighthouse_version="12.0.0",
        # Opportunities
        render_blocking_savings_ms=2500,
        render_blocking_resources=[
            RenderBlockingResource(
                url="https://cdn.example.com/styles.css",
                resource_type="CSS",
                transfer_size_bytes=150000,
                estimated_savings_ms=800,
            ),
            RenderBlockingResource(
                url="https://cdn.example.com/app.js",
                resource_type="JS",
                transfer_size_bytes=450000,
                estimated_savings_ms=1200,
            ),
        ],
        unused_css_bytes=350000,
        unused_js_bytes=800000,
        image_savings_bytes=500000,
        image_opportunities=[
            ImageOpportunity(
                url="https://example.com/images/hero.jpg",
                issue="oversized",
                estimated_bytes_savings=200000,
                is_lcp_element=True,
            ),
        ],
        oversized_image_count=5,
        third_party_transfer_bytes=500000,
        third_party_main_thread_ms=1200,
        third_party_entities=[
            ThirdPartyEntity(
                domain="www.googletagmanager.com",
                provider="Google Tag Manager",
                transfer_bytes=200000,
                main_thread_ms=400,
                blocking_time_ms=150,
            ),
            ThirdPartyEntity(
                domain="connect.facebook.net",
                provider="Facebook",
                transfer_bytes=180000,
                main_thread_ms=500,
                blocking_time_ms=200,
            ),
        ],
        font_display_issues=[
            FontIssue(
                url="https://fonts.googleapis.com/css?family=Roboto",
                issue="missing_font_display",
                detail="Font does not use font-display CSS",
            ),
        ],
        layout_shift_elements=[
            LayoutShiftElement(
                node_label="h1.hero-title",
                cls_contribution=0.15,
            ),
            LayoutShiftElement(
                node_label="div.banner",
                cls_contribution=0.12,
            ),
        ],
        run_warnings=[],
        psi_status="success",
    )


# ============================================================
# 3. no_field_data — lab only, no CrUX
# ============================================================

def make_no_field_data(url: str = "https://example.com/low-traffic") -> PerformanceSnapshot:
    """No CrUX field data, lab score 72 (moderate)."""
    return PerformanceSnapshot(
        url=url,
        requested_url=url,
        final_url=url,
        strategy="mobile",
        fetch_timestamp="2026-08-09T12:00:00Z",
        source="pagespeed_insights",
        field_data_available=False,
        field_data_scope="NONE",
        # No field metrics
        # Lab data present
        lab_performance_score=72,
        lab_seo_score=90,
        lab_accessibility_score=85,
        lab_best_practices_score=80,
        lab_lcp_ms=2800.0,
        lab_fcp_ms=1800.0,
        lab_tbt_ms=350.0,
        lab_cls=0.12,
        lab_speed_index_ms=3200.0,
        lab_tti_ms=4000.0,
        lighthouse_version="12.0.0",
        psi_status="success",
    )


# ============================================================
# 4. origin_field_only — origin-level CrUX only
# ============================================================

def make_origin_field_only(url: str = "https://example.com/product/123") -> PerformanceSnapshot:
    """Origin-level field data only (no URL-level CrUX)."""
    return PerformanceSnapshot(
        url=url,
        requested_url=url,
        final_url=url,
        strategy="mobile",
        fetch_timestamp="2026-08-09T12:00:00Z",
        source="pagespeed_insights",
        field_data_available=True,
        field_data_scope="ORIGIN",
        # No URL-level metrics
        # Origin-level metrics: NEEDS_IMPROVEMENT
        origin_field_lcp_ms=3200.0,
        origin_field_lcp_category="AVERAGE",
        origin_field_inp_ms=280.0,
        origin_field_inp_category="AVERAGE",
        origin_field_cls=0.18,
        origin_field_cls_category="AVERAGE",
        # Lab data
        lab_performance_score=65,
        lab_lcp_ms=3500.0,
        lab_tbt_ms=400.0,
        lab_cls=0.15,
        lighthouse_version="12.0.0",
        psi_status="success",
    )


# ============================================================
# 5. partial_lighthouse — missing some audits
# ============================================================

def make_partial_lighthouse(url: str = "https://example.com/partial") -> PerformanceSnapshot:
    """Lighthouse ran but missing TBT, CLS, render-blocking audits."""
    return PerformanceSnapshot(
        url=url,
        requested_url=url,
        final_url=url,
        strategy="mobile",
        fetch_timestamp="2026-08-09T12:00:00Z",
        source="pagespeed_insights",
        field_data_available=True,
        field_data_scope="URL",
        field_lcp_ms=2200.0,
        field_lcp_category="FAST",
        field_inp_ms=180.0,
        field_inp_category="FAST",
        field_cls=0.08,
        field_cls_category="FAST",
        lab_performance_score=85,
        lab_lcp_ms=2400.0,
        lab_fcp_ms=1600.0,
        # TBT, CLS, Speed Index, TTI NOT available
        lighthouse_version="12.0.0",
        render_blocking_savings_ms=0,
        render_blocking_resources=[],  # Empty = audit didn't produce items
        psi_status="success",
    )


# ============================================================
# 6. api_error — PSI API error
# ============================================================

def make_api_error(url: str = "https://example.com/error-page") -> PerformanceSnapshot:
    """PSI API returned an error."""
    return PerformanceSnapshot(
        url=url,
        requested_url=url,
        strategy="mobile",
        psi_status="error",
        error="PSI server error (HTTP 500)",
        run_warnings=["PSI server error (HTTP 500)"],
    )


# ============================================================
# 7. rate_limit — rate limit
# ============================================================

def make_rate_limit(url: str = "https://example.com/blocked") -> PerformanceSnapshot:
    """PSI API rate limited."""
    return PerformanceSnapshot(
        url=url,
        requested_url=url,
        strategy="mobile",
        psi_status="error",
        error="PSI rate limit exceeded (HTTP 429)",
        run_warnings=["PSI rate limit exceeded (HTTP 429)"],
    )


# ============================================================
# 8. redirected_url — final_url differs
# ============================================================

def make_redirected(url: str = "https://example.com/old-page",
                    final_url: str = "https://example.com/new-page") -> PerformanceSnapshot:
    """URL was redirected during PSI test."""
    snap = make_good_mobile(url)
    snap = replace(snap, final_url=final_url)
    return snap


# ============================================================
# 9. third_party_heavy — many third-party scripts
# ============================================================

def make_third_party_heavy(url: str = "https://example.com/ad-heavy") -> PerformanceSnapshot:
    """Page with heavy third-party script impact."""
    return PerformanceSnapshot(
        url=url,
        requested_url=url,
        final_url=url,
        strategy="mobile",
        fetch_timestamp="2026-08-09T12:00:00Z",
        source="pagespeed_insights",
        field_data_available=True,
        field_data_scope="URL",
        field_lcp_ms=2500.0,
        field_lcp_category="FAST",
        field_inp_ms=300.0,
        field_inp_category="AVERAGE",
        field_cls=0.15,
        field_cls_category="AVERAGE",
        lab_performance_score=58,
        lab_lcp_ms=2600.0,
        lab_tbt_ms=600.0,
        lab_cls=0.12,
        lighthouse_version="12.0.0",
        render_blocking_savings_ms=800,
        render_blocking_resources=[],
        unused_js_bytes=200000,
        third_party_transfer_bytes=800000,
        third_party_main_thread_ms=1500,
        third_party_entities=[
            ThirdPartyEntity(
                domain="www.googletagmanager.com",
                provider="Google Tag Manager",
                transfer_bytes=200000,
                main_thread_ms=300,
                blocking_time_ms=100,
            ),
            ThirdPartyEntity(
                domain="connect.facebook.net",
                provider="Facebook",
                transfer_bytes=250000,
                main_thread_ms=400,
                blocking_time_ms=150,
            ),
            ThirdPartyEntity(
                domain="cdn.taboola.com",
                provider="Taboola",
                transfer_bytes=150000,
                main_thread_ms=350,
                blocking_time_ms=200,
            ),
            ThirdPartyEntity(
                domain="ads.example-ad-network.com",
                provider="Unknown",
                transfer_bytes=200000,
                main_thread_ms=450,
                blocking_time_ms=250,
            ),
        ],
        psi_status="success",
    )


# ============================================================
# 10. image_heavy — many image optimization opportunities
# ============================================================

def make_image_heavy(url: str = "https://example.com/gallery") -> PerformanceSnapshot:
    """Image-heavy page with optimization opportunities."""
    return PerformanceSnapshot(
        url=url,
        requested_url=url,
        final_url=url,
        strategy="mobile",
        fetch_timestamp="2026-08-09T12:00:00Z",
        source="pagespeed_insights",
        field_data_available=False,
        field_data_scope="NONE",
        lab_performance_score=55,
        lab_lcp_ms=4000.0,
        lab_tbt_ms=200.0,
        lab_cls=0.05,
        lighthouse_version="12.0.0",
        image_savings_bytes=800000,
        oversized_image_count=8,
        image_opportunities=[
            ImageOpportunity(
                url="https://example.com/images/photo1.jpg",
                issue="oversized",
                estimated_bytes_savings=250000,
                is_lcp_element=False,
            ),
            ImageOpportunity(
                url="https://example.com/images/photo2.png",
                issue="modern_format",
                estimated_bytes_savings=180000,
                is_lcp_element=False,
            ),
            ImageOpportunity(
                url="https://example.com/images/hero-banner.jpg",
                issue="oversized",
                estimated_bytes_savings=300000,
                is_lcp_element=True,  # LCP element — do NOT lazy-load
            ),
        ],
        psi_status="success",
    )


# ============================================================
# 11. cls_font_issue — font display issues + CLS
# ============================================================

def make_cls_font_issue(url: str = "https://example.com/font-issue") -> PerformanceSnapshot:
    """Page with font-display issues and CLS from fonts."""
    return PerformanceSnapshot(
        url=url,
        requested_url=url,
        final_url=url,
        strategy="mobile",
        fetch_timestamp="2026-08-09T12:00:00Z",
        source="pagespeed_insights",
        field_data_available=False,
        field_data_scope="NONE",
        lab_performance_score=62,
        lab_cls=0.35,  # High CLS
        lighthouse_version="12.0.0",
        font_display_issues=[
            FontIssue(
                url="https://fonts.googleapis.com/css2?family=Inter",
                issue="missing_font_display",
                detail="Font does not use font-display CSS",
            ),
            FontIssue(
                url="https://fonts.googleapis.com/css2?family=Playfair+Display",
                issue="missing_font_display",
                detail="Font does not use font-display CSS",
            ),
            FontIssue(
                url="https://cdn.example.com/fonts/custom.woff2",
                issue="missing_font_display",
                detail="Font does not use font-display CSS",
            ),
        ],
        layout_shift_elements=[
            LayoutShiftElement(
                node_label="h1.heading",
                cls_contribution=0.12,
            ),
            LayoutShiftElement(
                node_label="span.title-text",
                cls_contribution=0.08,
            ),
            LayoutShiftElement(
                node_label="div.banner-ad",
                cls_contribution=0.10,
            ),
        ],
        psi_status="success",
    )


# ============================================================
# Helpers for building test data dicts
# ============================================================

def make_psi_cache(
    snapshots: list[PerformanceSnapshot],
    strategy: str = "mobile",
) -> dict[tuple[str, str], PerformanceSnapshot]:
    """Build a PSI cache dict from a list of snapshots."""
    cache = {}
    for snap in snapshots:
        key = (snap.url.rstrip("/").lower(), strategy)
        cache[key] = snap
    return cache


def make_data_dict(
    snapshots: list[PerformanceSnapshot],
    strategy: str = "mobile",
) -> dict:
    """Build the complete data dict that adapters expect."""
    return {
        "_psi_cache": make_psi_cache(snapshots, strategy),
        "psi_strategy": strategy,
        "_psi_provider": None,  # Not needed for unit tests
        "psi_sampled": [
            (PageContext(url=s.url, status_code=200), "test")
            for s in snapshots
        ],
    }


def make_site_context(base_url: str = "https://example.com") -> SiteContext:
    """Minimal site context for performance tests."""
    return SiteContext(base_url=base_url)


def make_page_contexts(urls: list[str]) -> list[PageContext]:
    """Minimal page contexts for performance tests."""
    return [PageContext(url=u, status_code=200) for u in urls]


# ============================================================
# All fixture builders registry
# ============================================================

ALL_FIXTURES: dict[str, callable] = {
    "good_mobile": make_good_mobile,
    "poor_mobile": make_poor_mobile,
    "no_field_data": make_no_field_data,
    "origin_field_only": make_origin_field_only,
    "partial_lighthouse": make_partial_lighthouse,
    "api_error": make_api_error,
    "rate_limit": make_rate_limit,
    "redirected_url": lambda: make_redirected(),
    "third_party_heavy": make_third_party_heavy,
    "image_heavy": make_image_heavy,
    "cls_font_issue": make_cls_font_issue,
}
