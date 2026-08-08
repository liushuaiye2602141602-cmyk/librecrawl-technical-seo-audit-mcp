"""RuleRunner — orchestrates rule evaluation across site + pages.

Phase 1+2: Uses LibreCrawlDataProvider (existing export data only, no HTTP
re-fetch) + CompatibilityHarness (18 Phase 1 EXISTING_FULL + 14 Phase 2
local adapters) + CoverageManager (80-row coverage matrix).

Usage:
    runner = RuleRunner(registry, providers, harness)
    findings, coverage = runner.run(site_data, pages_data, links_data)
"""

from dataclasses import dataclass, field
from typing import Optional

from audit_rules.models import RuleDefinition, Finding, CoverageRow
from audit_rules.context import SiteContext, PageContext
from audit_rules.providers.base import DataProvider
from audit_rules.providers.librecrawl_provider import LibreCrawlDataProvider
from audit_rules.adapters import CompatibilityHarness
from audit_rules.coverage import CoverageManager


@dataclass
class RuleRunner:
    """Orchestrates rule evaluation: data → adapters → findings → coverage.

    In Phase 1, the runner:
      1. Creates SiteContext + PageContexts from LibreCrawl export data
      2. Runs CompatibilityHarness to get findings from EXISTING_FULL rules
      3. Computes CoverageManager to get 80-row coverage matrix
    """

    registry: list[RuleDefinition]
    providers: dict[str, DataProvider] = field(default_factory=dict)
    harness: Optional[CompatibilityHarness] = None

    def __post_init__(self):
        if self.harness is None:
            self.harness = CompatibilityHarness(self.registry)

    def run(
        self,
        site_data: dict | None = None,
        pages: list[dict] | None = None,
        links: list[dict] | None = None,
        existing_data: dict | None = None,
        base_url: str = "",
        completeness: dict | None = None,
    ) -> tuple[list[Finding], list[CoverageRow]]:
        """Run the full audit pipeline.

        Args:
            site_data: _site_check() result dict (robots.txt, sitemap, redirects)
            pages: List of page dicts from LibreCrawl export (30+ fields each)
            links: Flat links list from crawl
            existing_data: Additional existing check output
                           (extended_checks, crawl metadata, etc.)
            base_url: The seed URL
            completeness: Crawl completeness dict from sitemap reconciliation

        Returns:
            (findings, coverage_rows) tuple
        """
        site_data = site_data or {}
        pages = pages or []
        links = links or []
        existing_data = existing_data or {}

        # Step 1: Create contexts from LibreCrawl data
        librecrawl = LibreCrawlDataProvider(pages, site_data, links)
        site_ctx, page_contexts = librecrawl.create_contexts(base_url, completeness)

        # Step 2: Enrich with other providers (Phase 3+ — no-op in Phase 1)
        available_providers = {"LibreCrawl"}
        for name, provider in self.providers.items():
            if provider.is_available():
                available_providers.add(name)
                try:
                    provider.enrich_site(site_ctx)
                    for pctx in page_contexts:
                        provider.enrich_page(pctx)
                except Exception:
                    # Provider failed → mark unavailable, rules will get NOT_CHECKED
                    available_providers.discard(name)

        # Step 3: Run adapters to get findings (Phase 1 + Phase 2)
        findings = self.harness.run(
            site_ctx, page_contexts, existing_data,
        )

        # Step 4: Release heavy fields from all pages
        for pctx in page_contexts:
            pctx.release_heavy()

        # Step 5: Compute coverage matrix
        mgr = CoverageManager(self.registry)
        coverage_rows = mgr.compute(
            site_ctx, page_contexts, findings,
            providers_available=available_providers,
        )

        return findings, coverage_rows

    def run_from_export(
        self,
        export_data: dict,
        base_url: str = "",
    ) -> tuple[list[Finding], list[CoverageRow]]:
        """Convenience: run from a single export data dict.

        The export_data dict is the structure returned by LibreCrawl's
        export endpoint, containing site_check, pages, links, crawl, etc.

        Args:
            export_data: Full LibreCrawl export dict
            base_url: The seed URL

        Returns:
            (findings, coverage_rows) tuple
        """
        return self.run(
            site_data=export_data.get("site_check", {}),
            pages=export_data.get("pages", []),
            links=export_data.get("links", []),
            existing_data={
                "extended_checks": export_data.get("extended_checks", {}),
                "crawl": export_data.get("crawl", {}),
            },
            base_url=base_url,
            completeness=export_data.get("completeness"),
        )
