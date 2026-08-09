"""PageSpeedDataProvider — wraps existing PSI implementation for V3 pipeline.

Design:
  - WRAPS the shared psi_client.fetch_pagespeed() — no duplicate HTTP code.
  - In-memory session cache: one (URL, strategy) → one API call.
  - ALL rule checks share the same PerformanceSnapshot cache.
  - Failure semantics: missing API key → provider unavailable; partial data
    → partial execution; HTTP errors → individual URL errors (not site failures).

Config:
  - PAGESPEED_API_KEY: API key (env var)
  - PSI_SAMPLE_LIMIT: max URLs to test (default 20)
  - PSI_STRATEGIES: "mobile" or "mobile,desktop" (default "mobile")
  - MASTER_AUDIT_PSI_ENABLED: gate within V3 pipeline (default True when V3 on)
"""

from __future__ import annotations

import os
import time
import logging
from typing import Optional, Callable

from audit_rules.context import SiteContext, PageContext
from audit_rules.providers.base import DataProvider
from audit_rules.providers.performance_snapshot import (
    PerformanceSnapshot,
    RenderBlockingResource,
    ImageOpportunity,
    ThirdPartyEntity,
    FontIssue,
    LayoutShiftElement,
)

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────
DEFAULT_PSI_SAMPLE_LIMIT = 20
MAX_PSI_SAMPLE_LIMIT = 100
VALID_PSI_STRATEGIES = ("mobile", "desktop")


def _parse_sample_limit(value: object) -> int:
    """Return a bounded positive PSI sample limit with a safe fallback."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return DEFAULT_PSI_SAMPLE_LIMIT
    if parsed <= 0:
        return DEFAULT_PSI_SAMPLE_LIMIT
    return min(parsed, MAX_PSI_SAMPLE_LIMIT)


def _parse_strategies(value: object) -> list[str]:
    """Normalize supported strategies, preserving caller order."""
    raw = str(value or "")
    strategies: list[str] = []
    for item in raw.split(","):
        strategy = item.strip().lower()
        if strategy in VALID_PSI_STRATEGIES and strategy not in strategies:
            strategies.append(strategy)
    return strategies or ["mobile"]


PSI_SAMPLE_LIMIT = _parse_sample_limit(os.getenv("PSI_SAMPLE_LIMIT", "20"))
PSI_STRATEGIES = os.getenv("PSI_STRATEGIES", "mobile")
MASTER_AUDIT_PSI_ENABLED = os.getenv("MASTER_AUDIT_PSI_ENABLED", "true").lower() == "true"


def _is_psi_enabled() -> bool:
    """Check if PSI provider is enabled (respects feature flag)."""
    v3_enabled = os.getenv("MASTER_AUDIT_V3_ENABLED", "false").lower() == "true"
    psi_enabled = os.getenv("MASTER_AUDIT_PSI_ENABLED", "true").lower() == "true"
    return v3_enabled and psi_enabled


def _get_strategies() -> list[str]:
    """Parse PSI_STRATEGIES env var into list."""
    return _parse_strategies(os.getenv("PSI_STRATEGIES", PSI_STRATEGIES))


# ── Sampling ───────────────────────────────────────────────────────────────

def select_performance_sample(
    page_contexts: list[PageContext],
    limit: int = PSI_SAMPLE_LIMIT,
) -> list[tuple[PageContext, str]]:
    """Template-aware representative URL sampling.

    Selects up to `limit` pages covering diverse URL patterns.
    Deterministic: same input → same sample (sorted selection).

    Categories (in priority order):
      - homepage
      - category/archive
      - product/service
      - solution/industry
      - blog/article
      - contact/about
      - high internal-link pages
      - deep pages (depth >= 4)
      - pages with large HTML or images
      - different language directories
      - different templates (by URL structure)

    Returns:
        List of (PageContext, sampling_reason) tuples.
    """
    if not page_contexts:
        return []

    # Filter to 200-status pages
    ok_pages = [p for p in page_contexts if p.status_code == 200]
    if not ok_pages:
        return []

    # ── Phase 1: identify candidates by category ──
    buckets: dict[str, list[PageContext]] = {
        "homepage": [],
        "category_archive": [],
        "product_service": [],
        "solution_industry": [],
        "blog_article": [],
        "contact_about": [],
        "high_internal_links": [],
        "deep_page": [],
        "large_page": [],
        "language_dir": [],
        "other": [],
    }

    # URL pattern detectors
    import re
    from urllib.parse import urlparse

    # Count pages for percentile calculations
    link_counts = [p.internal_links_count for p in ok_pages if p.internal_links_count > 0]
    link_75th = sorted(link_counts)[len(link_counts) * 3 // 4] if link_counts else 10
    word_counts = [p.word_count for p in ok_pages if p.word_count > 0]
    word_75th = sorted(word_counts)[len(word_counts) * 3 // 4] if word_counts else 3000

    # Collect unique language directories
    lang_dirs = set()
    for p in ok_pages:
        parsed = urlparse(p.url)
        segments = parsed.path.strip("/").split("/")
        if segments and len(segments[0]) == 2 and segments[0].islower():
            lang_dirs.add(segments[0])

    for p in ok_pages:
        url_lower = p.url.lower()
        parsed = urlparse(p.url)
        path = parsed.path.strip("/")

        # Homepage
        if path == "" or path == "/":
            buckets["homepage"].append(p)
            continue

        segments = path.split("/")

        # Language directory
        if segments[0] in lang_dirs and len(segments) > 1:
            buckets["language_dir"].append(p)
            continue

        # Category/archive patterns
        if any(pat in url_lower for pat in
               ("/category/", "/cat/", "/collection/", "/archive/",
                "/shop/", "/store/", "/products/", "/product-category/",
                "/tag/", "/topic/", "/type/")):
            buckets["category_archive"].append(p)
            continue

        # Product/service patterns
        if any(pat in url_lower for pat in
               ("/product/", "/item/", "/p/", "/products/", "/service/",
                "/services/", "/solution/", "/solutions/")):
            buckets["product_service"].append(p)
            continue

        # Blog/article patterns
        if any(pat in url_lower for pat in
               ("/blog/", "/article/", "/post/", "/news/", "/insights/",
                "/guide/", "/tutorial/", "/resource/", "/resources/")):
            buckets["blog_article"].append(p)
            continue

        # Contact/about patterns
        if any(pat in url_lower for pat in
               ("/contact", "/about", "/team", "/location", "/locations",
                "/office", "/offices", "/support")):
            buckets["contact_about"].append(p)
            continue

        # Fallback: look at URL structure for template detection
        # Deep page
        if p.depth >= 4:
            buckets["deep_page"].append(p)
            continue

        # High internal links
        if p.internal_links_count >= link_75th:
            buckets["high_internal_links"].append(p)
            continue

        # Large page
        if p.word_count >= word_75th:
            buckets["large_page"].append(p)
            continue

        buckets["other"].append(p)

    # ── Phase 2: pick from each bucket, maintaining diversity ──
    selected: list[tuple[PageContext, str]] = []

    # Priority ordering for selection
    priority = [
        "homepage", "category_archive", "product_service", "solution_industry",
        "blog_article", "contact_about", "high_internal_links",
        "deep_page", "large_page", "language_dir", "other",
    ]

    # First pass: pick 1 from each non-empty bucket (guarantees coverage)
    for bucket_key in priority:
        bucket = buckets.get(bucket_key, [])
        if bucket and len(selected) < limit:
            selected.append((bucket[0], bucket_key))
            buckets[bucket_key] = bucket[1:]  # Remove the picked item

    # Second pass: round-robin from remaining buckets
    remaining = limit - len(selected)
    if remaining > 0:
        all_remaining = []
        for bucket_key in priority:
            all_remaining.extend([(p, bucket_key) for p in buckets.get(bucket_key, [])])
        # Deterministic: sort by URL
        all_remaining.sort(key=lambda x: x[0].url)
        selected.extend(all_remaining[:remaining])

    logger.info(
        "Performance sample: %d URLs selected from %d candidates (limit=%d)",
        len(selected), len(ok_pages), limit,
    )
    return selected


# ── Provider ───────────────────────────────────────────────────────────────

class PageSpeedDataProvider(DataProvider):
    """PageSpeed Insights data provider for V3 pipeline.

    Wraps the shared psi_client to fetch performance data. Maintains
    an in-memory cache keyed by (normalized_url, strategy) so multiple
    rule checks share results without duplicate API calls.

    Usage:
        provider = PageSpeedDataProvider()
        provider.enrich_site(site_ctx)
        snap = provider.get_snapshot("https://example.com", "mobile")
    """

    def __init__(
        self,
        sample_limit: int | None = None,
        strategies: list[str] | None = None,
        api_key: str = "",
    ):
        configured_limit = (
            os.getenv("PSI_SAMPLE_LIMIT", str(PSI_SAMPLE_LIMIT))
            if sample_limit is None
            else sample_limit
        )
        self._sample_limit = _parse_sample_limit(configured_limit)
        self._strategies = (
            _parse_strategies(",".join(strategies))
            if strategies is not None
            else _get_strategies()
        )
        self._api_key = api_key or os.getenv("PAGESPEED_API_KEY", "")
        self._available: bool | None = None
        # In-memory session cache: {(url, strategy): PerformanceSnapshot}
        self._cache: dict[tuple[str, str], PerformanceSnapshot] = {}

    # ── DataProvider interface ────────────────────────────────────────

    @property
    def name(self) -> str:
        return "PageSpeed API"

    def is_available(self) -> bool:
        """Provider is available when PSI API key is set and flag enabled."""
        if self._available is None:
            self._available = bool(self._api_key) and _is_psi_enabled()
        return self._available

    def healthcheck(self) -> bool:
        """Lightweight availability check (no API call)."""
        return self.is_available()

    def enrich_site(self, site_ctx: SiteContext) -> None:
        """No-op — PageSpeed is page-level, not site-level."""
        pass

    def enrich_page(self, page_ctx: PageContext) -> None:
        """No-op — snapshots are fetched lazily via get_snapshot()."""
        pass

    # ── Core API ──────────────────────────────────────────────────────

    def get_snapshot(
        self, url: str, strategy: str = "mobile", force_refresh: bool = False
    ) -> PerformanceSnapshot | None:
        """Get performance snapshot for a URL+strategy pair.

        Uses in-memory cache — same (URL, strategy) only fetches once.

        Args:
            url: Full URL to audit.
            strategy: "mobile" or "desktop".
            force_refresh: If True, bypass cache and re-fetch.

        Returns:
            PerformanceSnapshot, or None if provider unavailable or fetch error.
        """
        if not self.is_available():
            return None

        cache_key = (self._normalize_url(url), strategy)
        if not force_refresh and cache_key in self._cache:
            return self._cache[cache_key]

        snap = self._fetch_snapshot(url, strategy)
        if snap is not None:
            self._cache[cache_key] = snap
        return snap

    def get_snapshots_for_urls(
        self,
        urls: list[str],
        strategy: str = "mobile",
        delay: float = 1.0,
    ) -> list[PerformanceSnapshot]:
        """Fetch snapshots for multiple URLs with rate-limiting.

        Args:
            urls: List of URLs.
            strategy: "mobile" or "desktop".
            delay: Seconds between requests.

        Returns:
            List of PerformanceSnapshot (errors included as snapshots with error field).
        """
        results = []
        for i, url in enumerate(urls):
            snap = self.get_snapshot(url, strategy)
            if snap is None:
                snap = PerformanceSnapshot(
                    url=url, strategy=strategy, error="Provider unavailable",
                    psi_status="error",
                )
            results.append(snap)
            if i < len(urls) - 1:
                time.sleep(delay)
        return results

    def get_cached_snapshots(self) -> list[PerformanceSnapshot]:
        """Return all cached snapshots."""
        return list(self._cache.values())

    def clear_cache(self) -> None:
        """Clear the in-memory cache."""
        self._cache.clear()

    # ── Internal ──────────────────────────────────────────────────────

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for cache key (strip trailing slash, lowercase)."""
        return url.rstrip("/").lower()

    def _fetch_snapshot(
        self, url: str, strategy: str
    ) -> PerformanceSnapshot | None:
        """Fetch from PSI API and convert to PerformanceSnapshot."""
        from audit_rules.providers.psi_client import fetch_pagespeed

        raw = fetch_pagespeed(url, strategy=strategy, api_key=self._api_key)

        if "error" in raw:
            return PerformanceSnapshot(
                url=url,
                requested_url=url,
                strategy=strategy,
                source="pagespeed_insights",
                psi_status="error",
                error=raw["error"],
                run_warnings=[raw["error"]],
            )

        # ── Build PerformanceSnapshot ────────────────────────────────
        scores = raw.get("scores", {})
        field = raw.get("field_data_cwv", {})
        field_scope = raw.get("field_data_scope", "NONE")
        origin = raw.get("origin_field_data", {})
        lab = raw.get("lab_data", {})

        # Render-blocking resources
        rb_resources = [
            RenderBlockingResource(
                url=r.get("url", ""),
                resource_type=r.get("resource_type", ""),
                transfer_size_bytes=r.get("transfer_size_bytes", 0),
                estimated_savings_ms=r.get("estimated_savings_ms", 0),
            )
            for r in raw.get("render_blocking_resources", [])
        ]

        # Image opportunities
        img_opportunities = []
        for opp in raw.get("top_opportunities", []):
            opp_id = opp.get("id", "")
            if any(kw in opp_id.lower() for kw in
                   ("image", "modern-format", "offscreen", "responsive", "optimized")):
                img_opportunities.append(ImageOpportunity(
                    url=url,
                    issue=opp_id.replace("-", "_"),
                    estimated_bytes_savings=opp.get("savings_ms", 0) * 1000,
                ))

        # Third-party entities
        tp_entities = [
            ThirdPartyEntity(
                domain=e.get("domain", ""),
                provider=e.get("provider", ""),
                transfer_bytes=e.get("transfer_bytes", 0),
                main_thread_ms=e.get("main_thread_ms", 0),
                blocking_time_ms=e.get("blocking_time_ms", 0),
                request_count=e.get("request_count", 0),
            )
            for e in raw.get("third_party_entities", [])
        ]

        # Font issues
        font_issues = [
            FontIssue(
                url=f.get("url", ""),
                issue=f.get("issue", ""),
                detail=f.get("detail", ""),
            )
            for f in raw.get("font_issues", [])
        ]

        # Layout shifts
        layout_shifts = [
            LayoutShiftElement(
                node_label=e.get("node_label", ""),
                cls_contribution=e.get("cls_contribution", 0),
            )
            for e in raw.get("layout_shift_elements", [])
        ]

        return PerformanceSnapshot(
            url=url,
            requested_url=url,
            final_url=raw.get("final_url", url),
            strategy=strategy,
            fetch_timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            source="pagespeed_insights",
            # Field data
            field_data_available=field_scope != "NONE",
            field_data_scope=field_scope,
            field_lcp_ms=field.get("LCP", {}).get("value"),
            field_lcp_category=field.get("LCP", {}).get("category", ""),
            field_inp_ms=field.get("INP", {}).get("value"),
            field_inp_category=field.get("INP", {}).get("category", ""),
            field_cls=field.get("CLS", {}).get("value"),
            field_cls_category=field.get("CLS", {}).get("category", ""),
            field_fcp_ms=field.get("FCP", {}).get("value"),
            field_fcp_category=field.get("FCP", {}).get("category", ""),
            field_ttfb_ms=field.get("TTFB", {}).get("value"),
            field_ttfb_category=field.get("TTFB", {}).get("category", ""),
            # Origin field data
            origin_field_lcp_ms=origin.get("LCP", {}).get("value"),
            origin_field_lcp_category=origin.get("LCP", {}).get("category", ""),
            origin_field_inp_ms=origin.get("INP", {}).get("value"),
            origin_field_inp_category=origin.get("INP", {}).get("category", ""),
            origin_field_cls=origin.get("CLS", {}).get("value"),
            origin_field_cls_category=origin.get("CLS", {}).get("category", ""),
            # Lab data
            lab_performance_score=scores.get("performance"),
            lab_seo_score=scores.get("seo"),
            lab_accessibility_score=scores.get("accessibility"),
            lab_best_practices_score=scores.get("best_practices"),
            lab_lcp_ms=lab.get("LCP_ms"),
            lab_fcp_ms=lab.get("FCP_ms"),
            lab_tbt_ms=lab.get("TBT_ms"),
            lab_cls=lab.get("CLS"),
            lab_speed_index_ms=lab.get("Speed_Index_ms"),
            lab_tti_ms=lab.get("TTI_ms"),
            lighthouse_version=raw.get("lighthouse_version", ""),
            # Opportunities
            render_blocking_savings_ms=raw.get("render_blocking_savings_ms", 0),
            render_blocking_resources=rb_resources,
            unused_css_bytes=raw.get("unused_css_bytes", 0),
            unused_js_bytes=raw.get("unused_js_bytes", 0),
            image_savings_bytes=raw.get("image_savings_bytes", 0),
            image_opportunities=img_opportunities,
            oversized_image_count=raw.get("oversized_image_count", 0),
            # Third-party
            third_party_transfer_bytes=raw.get("third_party_transfer_bytes", 0),
            third_party_main_thread_ms=raw.get("third_party_main_thread_ms", 0),
            third_party_entities=tp_entities,
            # Font/CLS
            font_display_issues=font_issues,
            layout_shift_elements=layout_shifts,
            # Diagnostics
            run_warnings=raw.get("run_warnings", []),
            psi_status="success",
        )
