"""LibreCrawlDataProvider — populates PageContext/SiteContext from crawl export data.

Phase 1: Uses EXISTING crawl export data ONLY. No HTTP re-fetch (Requirement 7).
Heavy fields are lazy-loaded per page and released after evaluation.
"""

from audit_rules.providers.base import DataProvider
from audit_rules.context import PageContext, SiteContext


class LibreCrawlDataProvider(DataProvider):
    """Data provider backed by LibreCrawl's export data (always available)."""

    def __init__(self, pages: list[dict], site_data: dict | None = None,
                 links: list[dict] | None = None):
        self._pages = pages
        self._site_data = site_data or {}
        self._links = links or []
        self._context_cache: dict[str, PageContext] = {}

    @property
    def name(self) -> str:
        return "LibreCrawl"

    def is_available(self) -> bool:
        """LibreCrawl is always available — it's the core data source."""
        return True

    def enrich_site(self, ctx: SiteContext) -> None:
        """Merge site_data into SiteContext (no-op if already populated)."""
        if self._site_data and not ctx._site_data:
            ctx._site_data = self._site_data

    def enrich_page(self, ctx: PageContext) -> None:
        """Phase 1: PageContext is pre-populated from export data.
        This method is a no-op for now. Heavy fields are lazy-loaded
        on first access to body_html/body_text/response_headers.
        """
        pass  # Already populated via PageContext.from_export()

    def create_contexts(self, base_url: str = "",
                        completeness: dict | None = None) -> tuple[SiteContext, list[PageContext]]:
        """Create SiteContext + PageContext list from LibreCrawl export data.

        Phase 1: Uses the existing `pages` list from LibreCrawl's export.
        No HTTP re-fetch. Heavy fields are lazy-loaded per page.

        Args:
            base_url: The seed URL of the crawl
            completeness: Crawl completeness dict from _compute_crawl_completeness()
                          or sitemap reconciliation

        Returns:
            (SiteContext, list[PageContext])
        """
        # Build site context
        site_ctx = SiteContext.from_site_check(self._site_data, base_url)

        if completeness:
            site_ctx.pages_crawled = completeness.get("pages_crawled", len(self._pages))
            site_ctx.sitemap_total = completeness.get("sitemap_total", 0)
            site_ctx.sitemap_only_count = completeness.get("sitemap_only_count", 0)
            site_ctx.sitemap_coverage_pct = completeness.get("sitemap_coverage_pct", 0.0)
            site_ctx.audit_complete = completeness.get("audit_complete", False)
            site_ctx.incomplete_reasons = completeness.get("incomplete_reasons", "")

        # Build page contexts (lightweight fields only)
        page_contexts = [PageContext.from_export(p) for p in self._pages]

        # Augment linked_from from unified inbound map
        self._augment_inbound(page_contexts)

        # Detect site profile
        site_ctx.site_profile = self._detect_profile(page_contexts)

        return site_ctx, page_contexts

    def _augment_inbound(self, contexts: list[PageContext]) -> None:
        """Build a reverse inbound-link map and augment linked_from counts.

        Uses the flat links list (primary) and per-page links_detailed (secondary).
        This mirrors the logic in server.py:_build_report (line ~408).
        """
        from collections import defaultdict
        inbound = defaultdict(set)

        # From flat links list
        for link in self._links:
            target = link.get("target_url") or link.get("to") or ""
            source = link.get("source_url") or link.get("from") or ""
            if target and source:
                inbound[target].add(source)

        # From per-page links_detailed
        for ctx in contexts:
            for link in (ctx.links_detailed or []):
                target = link.get("url") or link.get("href") or ""
                if target:
                    inbound[target].add(ctx.url)

        # Apply to contexts
        for ctx in contexts:
            sources = inbound.get(ctx.url, set())
            ctx.linked_from_count = max(ctx.linked_from_count, len(sources))

    def _detect_profile(self, contexts: list[PageContext]) -> str:
        """Detect site CMS/profile from generator tags and URL patterns."""
        wordpress_signals = 0
        for ctx in contexts:
            url_lower = ctx.url.lower()
            # WordPress URL patterns
            if any(p in url_lower for p in ("/wp-content/", "/wp-admin/", "/wp-json/",
                                               "/wp-login", "wp-includes")):
                wordpress_signals += 3
            # Check for WP-specific patterns in the export data
            raw = ctx._raw_export or {}
            if raw.get("generator") and "wordpress" in str(raw.get("generator", "")).lower():
                wordpress_signals += 5

        if wordpress_signals >= 5:
            return "wordpress"
        return "generic"
