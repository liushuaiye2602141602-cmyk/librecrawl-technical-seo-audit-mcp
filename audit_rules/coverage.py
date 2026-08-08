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
        executed_rule_ids: set[int] | None = None,
        partially_executed_rule_ids: set[int] | None = None,
        not_checked_reasons: dict[int, str] | None = None,
        manual_outcomes: dict | None = None,
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
        not_checked_reasons = not_checked_reasons or {}
        manual_outcomes = manual_outcomes or {}

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
                total_pages, providers_available, executed_rule_ids,
                partially_executed_rule_ids,
                not_checked_reasons,
                manual_outcomes,
            )

            # Count eligible pages
            eligible = self._count_eligible(rule, site_ctx, page_contexts)
            evaluated = self._count_evaluated(rule, exec_status, rule_findings, eligible)

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
        executed_rule_ids: set[int] | None,
        partially_executed_rule_ids: set[int] | None,
        not_checked_reasons: dict[int, str],
        manual_outcomes: dict,
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
            outcome = manual_outcomes.get(rule.audit_id)
            if outcome is not None:
                if outcome.status == "NOT_APPLICABLE":
                    return (ExecutionStatus.NOT_APPLICABLE, ResultStatus.UNKNOWN,
                            "Reviewer marked not applicable")
                result = {"PASS": ResultStatus.PASS,
                          "WARNING": ResultStatus.WARNING,
                          "FAIL": ResultStatus.FAIL}[outcome.status]
                return ExecutionStatus.EXECUTED_FULL, result, ""
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

        if executed_rule_ids is not None and rule.audit_id not in executed_rule_ids:
            return (
                ExecutionStatus.NOT_CHECKED,
                ResultStatus.UNKNOWN,
                not_checked_reasons.get(
                    rule.audit_id,
                    "No registered adapter executed",
                ),
            )

        partial_reason = ""
        if partially_executed_rule_ids and rule.audit_id in partially_executed_rule_ids:
            partial_reason = not_checked_reasons.get(rule.audit_id, "Partial evidence")

        # No findings → was it executed?
        if not findings:
            # If the rule is automatable and all required providers are available,
            # it was executed (ran and found nothing → pass)
            if rule.automatable:
                # Case A: Executed, found nothing → PASS
                status = (
                    ExecutionStatus.EXECUTED_PARTIAL
                    if partial_reason else ExecutionStatus.EXECUTED_FULL
                )
                return status, ResultStatus.PASS, partial_reason
            else:
                # Should not reach here (non-automatable is either NEW_MANUAL or EXTERNAL_DATA)
                return ExecutionStatus.NOT_CHECKED, ResultStatus.UNKNOWN, "Not executed"

        # Has findings → determine result from findings
        result = self._derive_result_from_findings(findings)

        # Findings are failures, not an execution trace.  A completed adapter
        # evaluated every eligible entity unless it explicitly reported partial
        # execution through partially_executed_rule_ids.
        exec_status = (
            ExecutionStatus.EXECUTED_PARTIAL
            if partial_reason else ExecutionStatus.EXECUTED_FULL
        )
        return exec_status, result, partial_reason

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
        eligible_count: int,
    ) -> int:
        """Count how many entities were actually evaluated."""
        if exec_status == ExecutionStatus.NOT_CHECKED:
            return 0
        if exec_status == ExecutionStatus.NOT_APPLICABLE:
            return 0

        if exec_status == ExecutionStatus.EXECUTED_FULL:
            return eligible_count

        # Partial executions currently expose only affected entities; use that
        # as a conservative lower bound rather than claiming full evaluation.
        urls = set(f.url for f in findings if f.url)

        if rule.scope == Scope.SITE:
            return 1 if findings else 0
        elif rule.scope == Scope.PAGE:
            return min(len(urls), eligible_count)
        elif rule.scope == Scope.LINK:
            return min(len(findings), eligible_count)
        else:
            return min(len(urls), eligible_count)
