"""Registry-driven Markdown workflow for genuinely manual audit rules."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from audit_rules.models import Finding, RuleDefinition


_STATUSES = ("PASS", "WARNING", "FAIL", "NOT_APPLICABLE")
_MARKER = re.compile(r"<!-- manual-review-rule:(\d+) -->")


class ManualReviewValidationError(ValueError):
    """Raised when a completed review is incomplete or has been tampered with."""


def _manual_rules(registry: list[RuleDefinition]) -> list[RuleDefinition]:
    return [rule for rule in registry if rule.impl_status.value == "NEW_MANUAL"]


def _site_label(site_url: str) -> str:
    value = str(site_url or "").replace("\r", " ").replace("\n", " ").strip()
    parsed = urlsplit(value if "://" in value else "//" + value)
    return (parsed.hostname or "unknown-site").lower()


def generate_manual_review_template(registry: list[RuleDefinition], site_url: str) -> str:
    """Generate a deterministic, parseable Markdown review template."""
    rules = _manual_rules(registry)
    lines = [
        "<!-- manual-review-v1 -->",
        "# Manual SEO Review",
        "",
        f"Site: {_site_label(site_url)}",
        f"Manual rules: {len(rules)}",
        "",
        "Select exactly one status per rule. WARNING and FAIL require evidence.",
        "Do not edit the HTML rule markers.",
        "",
    ]
    for rule in rules:
        lines.extend([
            f"<!-- manual-review-rule:{rule.audit_id} -->",
            f"## Rule {rule.audit_id}: {rule.title}",
            "",
            f"Rule ID: {rule.rule_id}",
            f"Priority: {rule.priority.value}",
            f"Description: {rule.description}",
            f"Acceptance criteria: {rule.acceptance_criteria}",
            "Status: [ ] PASS | [ ] WARNING | [ ] FAIL | [ ] NOT_APPLICABLE",
            "Evidence: <!-- enter evidence -->",
            "Notes: <!-- enter notes -->",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def _field(block: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}:\s*(.*)$", block, re.MULTILINE)
    return match.group(1).strip() if match else ""


def parse_manual_review(markdown: str, registry: list[RuleDefinition]) -> list[Finding]:
    """Validate a completed template and convert WARNING/FAIL to Findings."""
    if not isinstance(markdown, str) or not markdown.startswith("<!-- manual-review-v1 -->"):
        raise ManualReviewValidationError("unsupported manual review format")
    rules = _manual_rules(registry)
    by_id = {rule.audit_id: rule for rule in rules}
    matches = list(_MARKER.finditer(markdown))
    ids = [int(match.group(1)) for match in matches]
    if len(ids) != len(set(ids)):
        raise ManualReviewValidationError("duplicate manual rule marker")
    if set(ids) != set(by_id):
        raise ManualReviewValidationError("unknown or non-manual rule marker")

    findings: list[Finding] = []
    blocks = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        blocks[int(match.group(1))] = markdown[match.end():end]

    for rule in rules:
        block = blocks[rule.audit_id]
        status_line = _field(block, "Status")
        selected = [status for status in _STATUSES
                    if re.search(rf"\[[xX]\]\s*{status}(?:\s|\||$)", status_line)]
        if not selected:
            raise ManualReviewValidationError(
                f"manual review incomplete for rule {rule.audit_id}")
        if len(selected) != 1:
            raise ManualReviewValidationError(
                f"select exactly one status for rule {rule.audit_id}")
        status = selected[0]
        evidence = _field(block, "Evidence")
        notes = _field(block, "Notes")
        if evidence.startswith("<!--"):
            evidence = ""
        if notes.startswith("<!--"):
            notes = ""
        if status in {"WARNING", "FAIL"} and not evidence:
            raise ManualReviewValidationError(
                f"evidence required for rule {rule.audit_id}")
        if status not in {"WARNING", "FAIL"}:
            continue
        severity = "Warning" if status == "WARNING" else rule.severity.value
        findings.append(Finding(
            audit_id=rule.audit_id, rule_id=rule.rule_id, url="SITE",
            category=rule.category.value, priority=rule.priority.value,
            severity=severity, finding_type=rule.default_finding_type,
            scope=rule.scope.value,
            detected_value=f"Manual review result: {status}",
            expected_value=rule.acceptance_criteria, evidence=evidence,
            finding_detail=notes or evidence, remediation=rule.remediation,
            owner=rule.owner, acceptance_criteria=rule.acceptance_criteria,
            data_source="Manual Review", confidence=1.0,
        ))
    return findings
