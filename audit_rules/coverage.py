"""CoverageManager — produces 80 CoverageRow entries per audit.

The CoverageManager evaluates each rule in the registry against the
SiteContext + PageContexts + findings to determine:
  - ExecutionStatus: Was the rule executed? (fully, partially, not at all, N/A)
  - ResultStatus: What was the outcome? (pass, fail, warning, opportunity, unknown)

5 Key State Semantics:
  A. Fully executed + pass    → EXECUTED_FULL + PASS
  B. Fully executed + fail    → EXECUTED_FULL + FAIL
  C. Sampled/partial          → EXECUTED_PARTIAL + (PASS|FAIL|WARNING)
  D. Missing external data    → NOT_CHECKED + UNKNOWN (never PASS/FAIL)
  E. Not applicable to site   → NOT_APPLICABLE + UNKNOWN + reason
"""

from dataclasses import dataclass, field
from typing import Optional

from audit_rules.models import RuleDefinition, CoverageRow, Finding
from audit_rules.categories import (
    ExecutionStatus, ResultStatus, ImplStatus, Scope, DataSource
)
from audit_rules.context import SiteContext, PageContext


@dataclass
class CoverageManager:
    """Produces exactly 80 CoverageRow entries from registry + contexts + findings.

    Intended usage:
        manager = CoverageManager(registry)
        manager.compute(site_ctx, page_contexts, findings, providers_available)
        rows = manager.rows  # 80 CoverageRow entries
    """

    registry: list[RuleDefinition]
    rows: list[CoverageRow] = field(default_factory=list)

    def compute(
        self,
        site_ctx: SiteContext,
        page_contexts: list[PageContext],
        findings: list[Finding],
        providers_available: set[str] | None = None,
    ) -> list[CoverageRow]:
        """Compute 80 CoverageRow entries from registry + contexts + findings.

        Args:
            site_ctx: Site-level context (robots.txt, sitemap, CMS profile, etc.)
            page_contexts: All page contexts from the crawl
            findings: All findings produced by rule evaluation
            providers_available: Set of available provider names (e.g. {"LibreCrawl", "PageSpeed API"})

        Returns:
            Exactly 80 CoverageRow entries, sorted by audit_id
        """
        if providers_available is None:
            providers_available = {"LibreCrawl"}

        # Index findings by rule_id for O(1) lookup
        findings_by_rule: dict[int, list[Finding]] = {}
        for f in findings:
            findings_by_rule.setdefault(f.audit_id, []).append(f)

        total_pages = len(page_contexts)

        self.rows = []
        for rule in self.registry:
            rule_findings = findings_by_rule.get(rule.audit_id, [])
            exec_status, result_status, reason = self._evaluate_coverage(
                rule, rule_findings, site_ctx, page_contexts,
                total_pages, providers_available,
            )

            # Count eligible pages
            eligible = self._count_eligible(rule, site_ctx, page_contexts)
            evaluated = self._count_evaluated(rule, exec_status, rule_findings, total_pages)

            coverage_pct = 0.0
            if eligible > 0:
                coverage_pct = round(evaluated / eligible * 100, 1)

            row = CoverageRow(
                audit_id=rule.audit_id,
                rule_id=rule.rule_id,
                category=rule.category.value,
                check=rule.title,
                priority=rule.priority,
                scope=rule.scope,
                impl_status=rule.impl_status,
                execution_status=exec_status,
                result_status=result_status,
                eligible_count=eligible,
                evaluated_count=evaluated,
                coverage_pct=coverage_pct,
                finding_count=len(rule_findings),
                data_source=rule.required_data_sources[0] if rule.required_data_sources else "None",
                required_source=", ".join(rule.required_data_sources),
                not_checked_reason=reason,
                owner=rule.owner,
                remediation=rule.remediation,
                acceptance_criteria=rule.acceptance_criteria,
            )
            self.rows.append(row)

        return self.rows

    def _evaluate_coverage(
        self,
        rule: RuleDefinition,
        findings: list[Finding],
        site_ctx: SiteContext,
        page_contexts: list[PageContext],
        total_pages: int,
        providers_available: set[str],
    ) -> tuple[ExecutionStatus, ResultStatus, str]:
        """Determine ExecutionStatus + ResultStatus for a single rule.

        Returns:
            (execution_status, result_status, not_checked_reason)
        """
        # Case E: Not applicable — e.g. WordPress rule on generic site
        not_applicable_reason = self._check_applicability(rule, site_ctx)
        if not_applicable_reason:
            return ExecutionStatus.NOT_APPLICABLE, ResultStatus.UNKNOWN, not_applicable_reason

        # Case D: Manual-only rules → NOT_CHECKED + UNKNOWN
        if rule.impl_status == ImplStatus.NEW_MANUAL:
            return (
                ExecutionStatus.NOT_CHECKED,
                ResultStatus.UNKNOWN,
                f"Manual review required: {rule.owner or 'seo'}",
            )

        # Case D: Missing external data provider
        for src in rule.required_data_sources:
            if src != "LibreCrawl" and src not in providers_available:
                return (
                    ExecutionStatus.NOT_CHECKED,
                    ResultStatus.UNKNOWN,
                    f"Data source unavailable: {src}",
                )

        # No findings → was it executed?
        if not findings:
            # If the rule is automatable and all required providers are available,
            # it was executed (ran and found nothing → pass)
            if rule.automatable:
                # Case A: Executed, found nothing → PASS
                return ExecutionStatus.EXECUTED_FULL, ResultStatus.PASS, ""
            else:
                # Should not reach here (non-automatable is either NEW_MANUAL or EXTERNAL_DATA)
                return ExecutionStatus.NOT_CHECKED, ResultStatus.UNKNOWN, "Not executed"

        # Has findings → determine result from findings
        result = self._derive_result_from_findings(findings)

        # Determine execution level
        if rule.scope == Scope.SITE:
            # Site-scoped rules are always FULL (they check one thing: the site)
            exec_status = ExecutionStatus.EXECUTED_FULL
        elif rule.scope in (Scope.PAGE, Scope.TEMPLATE):
            # Check if all eligible pages were evaluated
            eligible = self._count_eligible(rule, None, page_contexts)  # site_ctx not needed for PAGE scope
            if eligible > 0 and len(findings) >= eligible:
                exec_status = ExecutionStatus.EXECUTED_FULL
            elif eligible > 0:
                exec_status = ExecutionStatus.EXECUTED_PARTIAL  # Case C
            else:
                exec_status = ExecutionStatus.EXECUTED_FULL
        elif rule.scope == Scope.LINK:
            exec_status = ExecutionStatus.EXECUTED_FULL
        elif rule.scope == Scope.RELATIONSHIP:
            exec_status = ExecutionStatus.EXECUTED_FULL
        else:
            exec_status = ExecutionStatus.EXECUTED_FULL

        return exec_status, result, ""

    def _check_applicability(self, rule: RuleDefinition, site_ctx: SiteContext) -> str:
        """Check if rule is applicable to this site. Returns reason if NOT_APPLICABLE."""
        # WordPress-specific rules on generic sites
        wp_rules = {36, 37, 38, 39, 64, 65, 66, 67, 68, 69}
        if rule.audit_id in wp_rules and site_ctx.site_profile != "wordpress":
            return f"Not applicable: WordPress-specific rule, site profile is '{site_ctx.site_profile}'"

        # Hreflang/multilingual rules on single-language sites
        hreflang_rules = {29, 32, 58, 59, 60}
        if rule.audit_id in hreflang_rules:
            has_hreflang = any(
                ctx.hreflang_summary and len(ctx.hreflang_summary) > 0
                for ctx in ([] if site_ctx is None else [])
            )
            # Actually we check page_contexts, not site_ctx
            # For now: never skip — hreflang may exist even if we don't detect it

        return ""

    def _derive_result_from_findings(self, findings: list[Finding]) -> ResultStatus:
        """Derive the worst result from a list of findings."""
        severity_order = {
            "Error": 4,
            "Warning": 3,
            "Opportunity": 2,
            "Info": 1,
        }
        worst = "Info"
        for f in findings:
            sev = f.severity if isinstance(f.severity, str) else str(f.severity)
            if severity_order.get(sev, 0) > severity_order.get(worst, 0):
                worst = sev

        mapping = {
            "Error": ResultStatus.FAIL,
            "Warning": ResultStatus.WARNING,
            "Opportunity": ResultStatus.OPPORTUNITY,
            "Info": ResultStatus.PASS,
        }
        return mapping.get(worst, ResultStatus.UNKNOWN)

    def _count_eligible(
        self,
        rule: RuleDefinition,
        site_ctx: SiteContext | None,
        page_contexts: list[PageContext],
    ) -> int:
        """Count eligible entities for this rule."""
        if rule.scope == Scope.SITE:
            return 1
        elif rule.scope in (Scope.PAGE, Scope.TEMPLATE):
            # Only indexable pages with 200 status
            return sum(1 for p in page_contexts if p.status_code == 200)
        elif rule.scope == Scope.LINK:
            return sum(p.internal_links_count + p.external_links_count for p in page_contexts)
        elif rule.scope == Scope.RELATIONSHIP:
            return len(page_contexts)
        return len(page_contexts)

    def _count_evaluated(
        self,
        rule: RuleDefinition,
        exec_status: ExecutionStatus,
        findings: list[Finding],
        total_pages: int,
    ) -> int:
        """Count how many entities were actually evaluated."""
        if exec_status == ExecutionStatus.NOT_CHECKED:
            return 0
        if exec_status == ExecutionStatus.NOT_APPLICABLE:
            return 0

        # Count unique URLs in findings
        urls = set(f.url for f in findings if f.url)

        if rule.scope == Scope.SITE:
            return 1 if findings else 1  # Site rules always evaluate once
        elif rule.scope == Scope.PAGE:
            return len(urls) if urls else total_pages
        elif rule.scope == Scope.LINK:
            return len(findings)
        else:
            return len(urls) if urls else total_pages
