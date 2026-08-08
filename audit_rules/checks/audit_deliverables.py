"""Rule 40 — Audit Deliverables: master-audit-tasks.csv generation.

Generates an actionable finding-level task CSV sorted by priority.
Only active when MASTER_AUDIT_V3_ENABLED=true.

CSV columns:
  audit_id, rule_id, category, priority, url, finding, evidence,
  seo_impact, remediation, owner, assignee, due_date, acceptance_criteria,
  status, verification_status
"""

import csv
import io
from typing import Optional

from audit_rules.models import RuleDefinition, Finding, CoverageRow
from audit_rules.categories import Priority
from audit_rules.adapters import DataUnavailableError
from audit_rules.context import PageContext, SiteContext


# Priority sort order: Critical first, then High, Medium, Low
PRIORITY_ORDER = {
    "Critical": 0,
    "High": 1,
    "Medium": 2,
    "Low": 3,
}

TASK_CSV_COLUMNS = [
    "audit_id",
    "rule_id",
    "category",
    "priority",
    "url",
    "finding",
    "evidence",
    "seo_impact",
    "remediation",
    "owner",
    "assignee",
    "due_date",
    "acceptance_criteria",
    "status",
    "verification_status",
]


def _safe_cell(value: object) -> object:
    """Neutralize spreadsheet formulas while preserving ordinary values."""
    if not isinstance(value, str):
        return value
    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def _sort_key(finding: Finding) -> tuple:
    """Sort findings: priority first, then by rule audit_id, then by URL."""
    priority_order = PRIORITY_ORDER.get(finding.priority, 99)
    return (priority_order, finding.audit_id, finding.url or "")


def generate_task_csv(
    findings: list[Finding],
    registry: list[RuleDefinition],
    domain: str = "",
    timestamp: str = "",
) -> str:
    """Generate master-audit-tasks.csv as a string.

    Args:
        findings: All findings from the V3 pipeline (all rules, not just EXISTING_FULL)
        registry: Full rule registry for remediation/owner/acceptance_criteria lookup
        domain: Domain name for filename (informational)
        timestamp: Timestamp for filename (informational)

    Returns:
        CSV string with header row and one row per finding, sorted by priority.
        Returns empty string if no findings.
    """
    if not findings:
        return ""

    # Build registry lookup
    rule_map: dict[str, RuleDefinition] = {r.rule_id: r for r in registry}

    # Sort findings by priority then audit_id then url
    sorted_findings = sorted(findings, key=_sort_key)

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")

    # Header
    writer.writerow(TASK_CSV_COLUMNS)

    for f in sorted_findings:
        rule = rule_map.get(f.rule_id)
        remediation = rule.remediation if rule else ""
        owner = rule.owner if rule else ""
        acceptance = rule.acceptance_criteria if rule else ""

        writer.writerow([_safe_cell(value) for value in [
            f.audit_id,
            f.rule_id,
            f.category or "",
            f.priority or "",
            f.url or "",
            f.finding_detail or f.detected_value or "",
            f.evidence or "",
            "",  # seo_impact — filled manually or by future enhancement
            f.remediation or remediation,
            f.owner or owner,
            f.owner or owner,
            "",  # due_date — intentionally assigned by the project owner
            acceptance,
            "open",  # default status
            "pending",
        ]])

    return output.getvalue()


def check_audit_deliverables(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 40 execution marker for the post-findings task artifact stage."""
    if data.get("deliverable_pipeline_available") is not True:
        raise DataUnavailableError("Deliverable pipeline unavailable")
    return []


def generate_task_csv_file(
    findings: list[Finding],
    registry: list[RuleDefinition],
    filepath: str,
) -> int:
    """Write master-audit-tasks.csv to disk.

    Args:
        findings: All findings from the V3 pipeline
        registry: Full rule registry
        filepath: Output file path

    Returns:
        Number of task rows written (excluding header).
    """
    csv_content = generate_task_csv(findings, registry)
    if not csv_content:
        return 0

    with open(filepath, "w", encoding="utf-8", newline="") as f:
        f.write(csv_content)

    # Count rows (excluding header)
    return max(0, len(csv_content.strip().split("\n")) - 1)
