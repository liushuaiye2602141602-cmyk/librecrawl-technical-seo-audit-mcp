"""RuleRunner — orchestrates rule evaluation across site + pages.

Phase 1+2+3: Uses LibreCrawlDataProvider (existing export data) +
CompatibilityHarness (18 P1 + 13 P2 + 8 P3 adapters) +
CoverageManager (80-row coverage matrix).

Phase 3 PageSpeed: PageSpeedDataProvider injected via self.providers;
samples pages, fetches PerformanceSnapshots, and injects cache into
the data dict for all 8 performance checks to share.

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
from audit_rules.providers.pagespeed_provider import (
    PageSpeedDataProvider, select_performance_sample,
)


# Rules whose required evidence is the bounded PageSpeed sample: evaluating N
# sampled URLs is partial execution, never full-site coverage.
_PSI_SAMPLED_RULES = {19, 21, 24, 61, 62, 63}


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
    last_shared_data: dict = field(default_factory=dict, init=False, repr=False)
    last_psi_summary: dict = field(default_factory=dict, init=False, repr=False)

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

        # The integration layer caches RuleRunner across audits. PSI cache is
        # audit-scoped evidence and must not leak URLs or results between sites.
        psi_provider = self.providers.get("PageSpeed API")
        if psi_provider is not None:
            psi_provider.clear_cache()

        # Step 2: Enrich with registered providers (Phase 3+ — no-op in Phase 1)
        available_providers = {"LibreCrawl"}
        if existing_data.get("snapshot_baseline_available") is True:
            available_providers.add("SnapshotBaseline")
        if any(
            isinstance((page._raw_export or {}).get("response_headers") or
                       (page._raw_export or {}).get("headers"), dict)
            and bool((page._raw_export or {}).get("response_headers") or
                     (page._raw_export or {}).get("headers"))
            for page in page_contexts
        ):
            available_providers.add("ResponseHeaders")
        if isinstance(site_data.get("tls_certificate"), dict):
            available_providers.add("TLSCertificate")
        for name, provider in self.providers.items():
            if provider.is_available():
                provider_name = provider.name
                provider_aliases = set(getattr(provider, "aliases", {provider_name}))
                available_providers.update(provider_aliases)
                try:
                    collect = getattr(provider, "collect", None)
                    if callable(collect):
                        if not collect(site_ctx, page_contexts, existing_data):
                            available_providers.difference_update(provider_aliases)
                    else:
                        provider.enrich_site(site_ctx)
                        for pctx in page_contexts:
                            provider.enrich_page(pctx)
                except Exception:
                    # Provider failed → mark unavailable, rules will get NOT_CHECKED
                    available_providers.difference_update(provider_aliases)

        # Step 3: Populate PSI cache if PageSpeedDataProvider is available
        if psi_provider is not None and psi_provider.is_available():
            strategies = psi_provider._strategies
            sampled = select_performance_sample(
                page_contexts, limit=psi_provider._sample_limit,
            )
            # Primary strategy (mobile) for all rule checks
            primary_strategy = strategies[0]
            sampled_urls = [ctx.url for ctx, reason in sampled]
            successful_snapshots = 0
            for url in sampled_urls:
                snap = psi_provider.get_snapshot(url, primary_strategy)
                if snap is not None and snap.psi_status == "success":
                    successful_snapshots += 1
            if successful_snapshots == 0:
                # Provider/network/quota failure is not an SEO PASS or FAIL.
                available_providers.discard("PageSpeed API")
            # Inject cache + strategy into data dict for all checks
            cache = psi_provider._cache.copy() if psi_provider._cache else {}
            existing_data["_psi_cache"] = cache
            existing_data["_psi_provider"] = psi_provider
            existing_data["psi_strategy"] = primary_strategy
            existing_data["psi_sampled"] = sampled
        else:
            existing_data["_psi_cache"] = {}
            existing_data["psi_strategy"] = "mobile"

        # Step 4: Run adapters to get findings (Phase 1 + Phase 2 + Phase 3)
        findings = self.harness.run(
            site_ctx, page_contexts, existing_data,
        )
        manual_outcomes = existing_data.get("manual_review_outcomes") or {}
        if manual_outcomes:
            from audit_rules.manual_review import findings_from_manual_outcomes
            findings.extend(findings_from_manual_outcomes(
                manual_outcomes, self.registry))

        # Step 5: Release heavy fields from all pages
        for pctx in page_contexts:
            pctx.release_heavy()

        # Step 5b: PSI-backed rules were evaluated on a bounded sample, not on
        # every eligible page. Mark them as partial execution and report the
        # sampled count as the evaluated count (sample != full coverage).
        psi_sampled = existing_data.get("psi_sampled") or []
        eligible_pages = sum(1 for p in page_contexts if p.status_code == 200)
        evaluated_overrides: dict[int, int] = {}
        if psi_sampled and eligible_pages and len(psi_sampled) < eligible_pages:
            from audit_rules.checks.performance import build_psi_execution_summary
            psi_summary = build_psi_execution_summary(
                existing_data.get("_psi_cache") or {},
                sampled_count=len(psi_sampled),
                eligible_pages=eligible_pages,
                strategy=existing_data.get("psi_strategy", "mobile"),
            )
            self.last_psi_summary = psi_summary
            for audit_id in _PSI_SAMPLED_RULES:
                self.harness.partially_completed_rule_ids.add(audit_id)
                self.harness.not_checked_reasons[audit_id] = (
                    f"PSI sampled {psi_summary['sampled_urls']} of "
                    f"{psi_summary['eligible_pages']} eligible pages "
                    f"({psi_summary['success']} successful, "
                    f"{psi_summary['timeout']} timeout, "
                    f"field_data_available={psi_summary['field_data_available']}); "
                    f"sampled evidence is partial execution"
                )
                evaluated_overrides[audit_id] = psi_summary["sampled_urls"]
        # Crawl-layer rules that run without external data still evaluate a
        # real positive count of units (sample != 0 evidence).
        if site_ctx.sitemap_found:
            evaluated_overrides[2] = 1
        if any(getattr(p, "word_count", None) is not None for p in page_contexts):
            evaluated_overrides[16] = eligible_pages
        # Rule 13 crawl-layer title scan evaluates every eligible page; the
        # GSC/Semrush search-intent layer is what makes the rule partial.
        evaluated_overrides[13] = eligible_pages

        # Step 6: Compute coverage matrix
        mgr = CoverageManager(self.registry)
        coverage_rows = mgr.compute(
            site_ctx, page_contexts, findings,
            providers_available=available_providers,
            executed_rule_ids=self.harness.completed_rule_ids,
            partially_executed_rule_ids=self.harness.partially_completed_rule_ids,
            not_checked_reasons=self.harness.not_checked_reasons,
            manual_outcomes=manual_outcomes,
            evaluated_overrides=evaluated_overrides,
        )

        self.last_shared_data = dict(existing_data)

        return findings, coverage_rows

    def run_from_export(
        self,
        export_data: dict,
        base_url: str = "",
        existing_data: dict | None = None,
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
        shared_data = {
            "extended_checks": export_data.get("extended_checks", {}),
            "crawl": export_data.get("crawl", {}),
        }
        shared_data.update(existing_data or {})
        return self.run(
            site_data=export_data.get("site_check", {}),
            pages=export_data.get("pages", []),
            links=export_data.get("links", []),
            existing_data=shared_data,
            base_url=base_url,
            completeness=export_data.get("completeness"),
        )
