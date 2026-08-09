"""Decision-oriented Markdown report for the complete V3 audit."""

from __future__ import annotations

from collections import Counter
from urllib.parse import urlsplit

from audit_rules.models import CoverageRow, Finding
from audit_rules.scoring import compute_audit_score


def _value(value) -> str:
    return str(value.value) if hasattr(value, "value") else str(value)


def _cell(value) -> str:
    return str(value or "").replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _finding_rows(findings: list[Finding], limit: int = 20) -> list[str]:
    rows = []
    for finding in findings[:limit]:
        result = "FAIL" if _value(finding.severity) == "Error" else _value(finding.severity).upper()
        rows.append(
            f"| {finding.audit_id} | {result} | {_cell(finding.priority)} | "
            f"{_cell(finding.url)} | {_cell(finding.finding_detail or finding.detected_value)} |")
    return rows or ["| — | PASS | — | — | No actionable findings in this section. |"]


def build_master_report(base_url: str, findings: list[Finding],
                        coverage_rows: list[CoverageRow]) -> str:
    """Build a deterministic report that keeps quality, coverage, and confidence separate."""
    score = compute_audit_score(findings, coverage_rows).to_dict()
    host = urlsplit(base_url).hostname or base_url or "unknown-site"
    statuses = Counter(_value(row.execution_status) for row in coverage_rows)
    results = Counter(_value(row.result_status) for row in coverage_rows)
    priority_levels = {"Critical": "P0", "High": "P1", "Medium": "P2", "Low": "P3"}
    ordered = sorted(findings, key=lambda item: (
        {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}.get(_value(item.priority), 9),
        item.audit_id, item.url or ""))
    missing = [row for row in coverage_rows if _value(row.execution_status) == "NOT_CHECKED"]
    manual = [row for row in coverage_rows if _value(row.impl_status) == "NEW_MANUAL"]

    lines = [
        "# Master SEO Audit Report", "", f"Site: {host}", "",
        "## Executive Summary", "",
        f"The audit produced {len(findings)} actionable findings across {len(coverage_rows)} registered rules. "
        "Error, Warning, Opportunity, Intentional, Manual, NOT_CHECKED, and NOT_APPLICABLE remain distinct states.", "",
        "## Status Legend", "",
        "- Error: a verified defect requiring correction.",
        "- Warning: a verified risk that needs review or remediation.",
        "- Opportunity: an evidence-backed improvement, not a defect.",
        "- Intentional: an observed condition explicitly accepted as expected.",
        "- Manual: a rule that requires human evidence and a recorded decision.",
        "- NOT_CHECKED: required evidence was unavailable or the review is pending; never treated as PASS.",
        "- NOT_APPLICABLE: the rule was evaluated and does not apply to this site.", "",
        "## Audit Score / Coverage / Confidence", "",
        f"- Audit Score: {score['overall_score'] if score['overall_score'] is not None else 'Unknown'} / 100",
        f"- Coverage: {score['coverage_pct']}%",
        f"- Confidence: {score['confidence']['label']} ({score['confidence']['pct'] if score['confidence']['pct'] is not None else 'Unknown'}%)",
        "", "## Priority Plan (P0 / P1 / P2 / P3)", "",
    ]
    for priority, label in priority_levels.items():
        count = sum(1 for finding in findings if _value(finding.priority) == priority)
        lines.append(f"- {label} ({priority}): {count} finding(s)")
    lines.extend(["", "## 80 Rule Coverage", "",
                  "| Execution status | Rules |", "|---|---:|"])
    lines.extend(f"| {_cell(key)} | {statuses[key]} |" for key in sorted(statuses))
    lines.extend(["", "| Result status | Rules |", "|---|---:|"])
    lines.extend(f"| {_cell(key)} | {results[key]} |" for key in sorted(results))
    lines.extend(["", "## Top Business Risks", "",
                  "| Rule | Result | Priority | URL/entity | Finding |",
                  "|---:|---|---|---|---|"])
    lines.extend(_finding_rows(ordered, 10))

    sections = [
        "Technical SEO", "Indexing / Crawling", "Architecture / Internal Links",
        "Content / Metadata", "International SEO", "Structured Data",
        "Performance / CWV", "Search Performance", "Backlinks", "WordPress",
        "Security",
    ]
    for heading in sections:
        lines.extend(["", f"## {heading}", "",
                      "See the coverage matrix and remediation plan for rule-level evidence and ownership."])

    lines.extend(["", "## Manual Review", "",
                  f"Manual rules: {len(manual)}. Completed reviews are ingested as PASS, WARNING, FAIL, or NOT_APPLICABLE; pending reviews remain NOT_CHECKED.",
                  "", "## Missing External Data", ""])
    if missing:
        lines.extend(f"- Rule {row.audit_id} ({_cell(row.rule_id)}): {_cell(row.not_checked_reason)}"
                     for row in missing)
    else:
        lines.append("- None.")
    lines.extend(["", "## Before / After Regression", "",
                  "Snapshot changes are reported in `crawl-diff.csv`; absence of a baseline is NOT_CHECKED, not PASS.",
                  "", "## Remediation Plan", "",
                  "| Rule | Result | Priority | URL/entity | Finding |",
                  "|---:|---|---|---|---|"])
    lines.extend(_finding_rows(ordered))
    lines.extend(["", "## Acceptance Criteria", ""])
    for finding in ordered[:20]:
        lines.append(f"- Rule {finding.audit_id}: {_cell(finding.acceptance_criteria)}")
    if not ordered:
        lines.append("- No open remediation acceptance criteria.")
    return "\n".join(lines).rstrip() + "\n"
