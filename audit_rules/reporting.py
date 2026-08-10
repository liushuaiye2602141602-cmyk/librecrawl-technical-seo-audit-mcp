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


def escape_markdown_literal(text: str) -> str:
    """Escape literal angle brackets so `<a href>` renders as text, not HTML."""
    return (str(text or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def task_type_for(
    severity: str,
    execution: str,
    result: str,
    *,
    is_manual_rule: bool = False,
) -> str:
    """Map a finding to the client task taxonomy.

    REMEDIATION   — confirmed defect/risk (Error/Warning in FAIL/WARNING rules)
    OPTIMIZATION  — evidence-backed opportunity
    DATA_REQUIRED — missing authoritative data (NOT_CHECKED rules)
    MANUAL_REVIEW — human judgment required
    MONITORING    — informational, non-actionable finding (Info severity)
    """
    if is_manual_rule:
        return "MANUAL_REVIEW"
    if execution == "NOT_CHECKED":
        return "DATA_REQUIRED"
    if execution == "NOT_APPLICABLE":
        return "MONITORING"
    sev = str(severity or "")
    if sev == "Error" or sev == "Warning":
        return "REMEDIATION"
    if sev == "Opportunity":
        return "OPTIMIZATION"
    return "MONITORING"


def truncate_evidence_examples(
    rows: list[dict],
    limit: int = 8,
) -> list[dict]:
    """Cap representative examples so the client PDF never dumps raw arrays."""
    return (rows or [])[:limit]


def schema_type_distribution(
    pages: list,
) -> dict[str, int]:
    """Count pages per detected JSON-LD type (for Rule 27 evidence)."""
    distribution: Counter = Counter()
    for page in pages:
        types = getattr(page, "json_ld_types", None) or []
        if not types:
            continue
        for schema_type in types:
            distribution[str(schema_type)] += 1
    return dict(distribution.most_common())


def aggregate_orphan_remediation(
    tasks: list[dict],
    *,
    audit_ids: tuple[int, ...] = (11, 45),
) -> list[dict]:
    """Merge Rule 11 + Rule 45 remediation rows into one deduplicated task.

    The diagnosis may stay in both audits, but the customer action is the
    same: add internal links. Returns a new task list with the aggregated
    row and both audit attributions retained.
    """
    orphan_tasks = [
        task for task in tasks
        if str(task.get("audit_id")) in {str(aid) for aid in audit_ids}
    ]
    if not orphan_tasks:
        return tasks
    urls = list(dict.fromkeys(
        task.get("url") for task in orphan_tasks if task.get("url")))
    first = orphan_tasks[0]
    aggregated = dict(first)
    aggregated.update({
        "audit_id": ",".join(str(aid) for aid in audit_ids),
        "rule_id": "internal_discoverability",
        "task_type": "REMEDIATION",
        "finding": (
            f"Fix internal discoverability for {len(urls)} orphan/"
            f"zero-inbound pages (Related Audits: #"
            + ", #".join(str(aid) for aid in audit_ids) + ")"
        ),
        "url": urls[0] if urls else "",
        "affected_url_count": len(urls),
        "affected_urls_sample": " | ".join(urls[:20]),
        "evidence": (
            "linked_from_count=0 on " + str(len(urls)) + " pages "
            "(HTML link graph; sitemap discovery is not an internal link)"
        ),
    })
    remaining = [
        task for task in tasks
        if str(task.get("audit_id")) not in {str(aid) for aid in audit_ids}
    ]
    return remaining + [aggregated]


def final_artifact_metrics(
    *,
    audit_rows: int,
    matrix_rows: int,
    coverage_rows: int,
    finding_rows: int,
    task_rows: int,
    manual_rows: int,
    performance_rows: int,
    pdf_pages: int,
    confirmed_remediation: int,
    optimization: int,
    data_required: int,
    manual_review_actions: int,
    p0: int,
    p1: int,
    p2: int,
    p3: int,
    score: float,
    coverage_pct: float,
    confidence_pct: float,
) -> dict:
    """Single object every report section references for artifact counts."""
    return {
        "audit_rows": audit_rows,
        "matrix_rows": matrix_rows,
        "coverage_rows": coverage_rows,
        "finding_rows": finding_rows,
        "task_rows": task_rows,
        "manual_rows": manual_rows,
        "performance_rows": performance_rows,
        "pdf_pages": pdf_pages,
        "confirmed_remediation": confirmed_remediation,
        "optimization": optimization,
        "data_required": data_required,
        "manual_review_actions": manual_review_actions,
        "p0": p0,
        "p1": p1,
        "p2": p2,
        "p3": p3,
        "score": score,
        "coverage_pct": coverage_pct,
        "confidence_pct": confidence_pct,
    }


def _finding_rows(findings: list[Finding], limit: int = 20) -> list[str]:
    rows = []
    for finding in findings[:limit]:
        result = "FAIL" if _value(finding.severity) == "Error" else _value(finding.severity).upper()
        rows.append(
            f"| {finding.audit_id} | {result} | {_cell(finding.priority)} | "
            f"{_cell(finding.url)} | {_cell(finding.finding_detail or finding.detected_value)} |")
    return rows or ["| — | PASS | — | — | No actionable findings in this section. |"]


def report_host(base_url: str) -> str:
    """Derive the report site identity from the audited URL.

    Site identity comes from the URL (or the replay source_url when
    rebuilding offline) — never from a customer-domain constant.
    """
    return urlsplit(base_url).hostname or base_url or "unknown-site"


def report_run_metrics(replay: dict, pages: list[dict]) -> dict:
    """Derive client report counts from the current run's authoritative
    artifacts (replay + crawl pages).

    Every count comes from this run: pages evaluated, sitemap URLs parsed and
    matched, and the sitemap lastmod scan size. Previous-site counts are never
    reused.
    """
    counts = replay.get("counts") or {}
    pages_crawled = int(counts.get("page_count") or len(pages) or 0)
    sitemap = replay.get("sitemap_reconciliation") or {}
    sitemap_total = int(sitemap.get("sitemap_total") or 0)
    sitemap_matched = int(sitemap.get("both_count") or 0)
    fetch_errors = sitemap.get("sitemap_fetch_errors") or []
    invalid_status = len(fetch_errors)
    return {
        "pages_crawled": pages_crawled,
        "sitemap_urls_parsed": sitemap_total,
        "sitemap_urls_matched": sitemap_matched,
        "sitemap_invalid_status": invalid_status,
        "sitemap_lastmod_scanned": sitemap_total,
    }


def remote_observation_counts(pages: list[dict]) -> dict:
    """URL-structure families observed in the current crawl pages."""
    html = sum(
        1 for page in pages
        if str(page.get("url") or "").rstrip("/").endswith(".html")
    )
    return {
        "html_suffix": html,
        "extensionless": len(pages) - html,
        "total": len(pages),
    }


def build_master_report(base_url: str, findings: list[Finding],
                        coverage_rows: list[CoverageRow]) -> str:
    """Build a deterministic report that keeps quality, coverage, and confidence separate."""
    score = compute_audit_score(findings, coverage_rows).to_dict()
    host = report_host(base_url)
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
