"""Rule 74: convert precomputed snapshot changes into audit findings."""

from __future__ import annotations

from audit_rules.categories import Severity
from audit_rules.context import PageContext, SiteContext
from audit_rules.models import Finding, RuleDefinition
from audit_rules.snapshot_diff import SnapshotChange


_CRITICAL_REGRESSION_TYPES = {
    "URL_REMOVED",
    "STATUS_CHANGED",
    "INDEXABILITY_CHANGED",
}


def check_regression_test(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Report fixed, regressed, new, and informational snapshot changes.

    Snapshot loading and comparison happen outside the check function. A missing
    baseline is represented by provider availability in CoverageManager, not by
    a fabricated pass or a synthetic SEO issue.
    """
    del site_ctx, page_contexts
    findings: list[Finding] = []
    for change in data.get("snapshot_changes") or []:
        if not isinstance(change, SnapshotChange):
            continue
        if change.classification == "UNCHANGED":
            continue
        severity = _severity_for_change(change)
        values = change.to_dict()
        findings.append(
            Finding(
                audit_id=rule.audit_id,
                rule_id=rule.rule_id,
                url=change.url,
                category=rule.category.value,
                priority=rule.priority.value,
                severity=severity.value,
                finding_type=rule.default_finding_type,
                scope=rule.scope.value,
                detected_value=(
                    f"{change.change_type}: {change.classification}"
                ),
                expected_value="No new crawl, indexability, metadata, or link regression",
                evidence=change.evidence,
                finding_detail=(
                    f"{change.change_type} on {change.url}; "
                    f"before={values['before']}; after={values['after']}"
                ),
                remediation=rule.remediation,
                owner=rule.owner,
                acceptance_criteria=rule.acceptance_criteria,
                data_source="LibreCrawl + SnapshotBaseline",
                confidence=1.0,
            )
        )
    return findings


def _severity_for_change(change: SnapshotChange) -> Severity:
    if (
        change.classification == "REGRESSED"
        and change.change_type in _CRITICAL_REGRESSION_TYPES
    ):
        return Severity.ERROR
    if change.classification in {"REGRESSED", "NEW_ISSUE"}:
        return Severity.WARNING
    return Severity.INFO
