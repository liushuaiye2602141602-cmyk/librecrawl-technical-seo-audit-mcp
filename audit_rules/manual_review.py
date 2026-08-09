"""Registry-driven, host-bound workflow for genuinely manual audit rules."""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlsplit

from audit_rules.models import Finding, RuleDefinition

_FINAL_STATUSES = ("PASS", "WARNING", "FAIL", "NOT_APPLICABLE")
_ALL_STATUSES = ("PENDING", "IN_REVIEW", *_FINAL_STATUSES)
_MARKER = re.compile(r"<!-- manual-review-rule:(\d+) -->")


class ManualReviewValidationError(ValueError):
    """Raised when a completed review is incomplete or has been tampered with."""


@dataclass(frozen=True)
class ManualReviewOutcome:
    audit_id: int
    status: str
    entity: str
    evidence: str
    notes: str
    reviewer: str
    reviewed_at: str


def _manual_rules(registry: list[RuleDefinition]) -> list[RuleDefinition]:
    return [rule for rule in registry if rule.impl_status.value == "NEW_MANUAL"]


def _site_label(site_url: str) -> str:
    value = str(site_url or "").replace("\r", " ").replace("\n", " ").strip()
    parsed = urlsplit(value if "://" in value else "//" + value)
    return (parsed.hostname or "unknown-site").lower().rstrip(".")


def generate_manual_review_template(registry: list[RuleDefinition], site_url: str) -> str:
    """Generate a deterministic, parseable Markdown review template."""
    rules = _manual_rules(registry)
    lines = [
        "<!-- manual-review-v1 -->", "# Manual SEO Review", "",
        f"Site: {_site_label(site_url)}", f"Manual rules: {len(rules)}", "",
        "Move each rule from PENDING/IN_REVIEW to one final status.",
        "WARNING and FAIL require evidence. Do not edit HTML rule markers.", "",
    ]
    for rule in rules:
        lines.extend([
            f"<!-- manual-review-rule:{rule.audit_id} -->",
            f"## Rule {rule.audit_id}: {rule.title}", "",
            f"Audit ID: {rule.audit_id}", f"Rule ID: {rule.rule_id}",
            f"Rule: {rule.title}", "URL/entity: SITE",
            f"Priority: {rule.priority.value}",
            f"Why manual: {rule.description}",
            f"Required evidence: {rule.tools or 'Reviewer-supplied evidence'}",
            f"Review instructions: {rule.notes or rule.description}",
            f"Acceptance criteria: {rule.acceptance_criteria}",
            ("Review status: [ ] PENDING | [ ] IN_REVIEW | [ ] PASS | "
             "[ ] WARNING | [ ] FAIL | [ ] NOT_APPLICABLE"),
            "Evidence: <!-- enter evidence -->",
            "Review notes: <!-- enter notes -->",
            "Reviewer: <!-- enter reviewer -->",
            "Reviewed at: <!-- ISO-8601 timestamp -->", "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def _field(block: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}:\s*(.*)$", block, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _entered(value: str) -> str:
    return "" if not value or value.startswith("<!--") else value


def parse_manual_review_outcomes(markdown: str, registry: list[RuleDefinition], *,
                                 expected_site: str = "") -> dict[int, ManualReviewOutcome]:
    """Validate a completed review and retain every final rule outcome."""
    if not isinstance(markdown, str) or not markdown.startswith("<!-- manual-review-v1 -->"):
        raise ManualReviewValidationError("unsupported manual review format")
    if expected_site and _site_label(_field(markdown, "Site")) != _site_label(expected_site):
        raise ManualReviewValidationError("manual review site mismatch")
    rules = _manual_rules(registry)
    by_id = {rule.audit_id: rule for rule in rules}
    matches = list(_MARKER.finditer(markdown))
    ids = [int(match.group(1)) for match in matches]
    if len(ids) != len(set(ids)):
        raise ManualReviewValidationError("duplicate manual rule marker")
    if set(ids) != set(by_id):
        raise ManualReviewValidationError("unknown or non-manual rule marker")
    blocks = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        blocks[int(match.group(1))] = markdown[match.end():end]
    outcomes = {}
    for rule in rules:
        block = blocks[rule.audit_id]
        status_line = _field(block, "Review status")
        selected = [status for status in _ALL_STATUSES
                    if re.search(rf"\[[xX]\]\s*{status}(?:\s|\||$)", status_line)]
        if not selected or selected[0] in {"PENDING", "IN_REVIEW"}:
            raise ManualReviewValidationError(f"manual review incomplete for rule {rule.audit_id}")
        if len(selected) != 1:
            raise ManualReviewValidationError(f"select exactly one status for rule {rule.audit_id}")
        status = selected[0]
        evidence = _entered(_field(block, "Evidence"))
        notes = _entered(_field(block, "Review notes"))
        reviewer = _entered(_field(block, "Reviewer"))
        reviewed_at = _entered(_field(block, "Reviewed at"))
        if status in {"WARNING", "FAIL"} and not evidence:
            raise ManualReviewValidationError(f"evidence required for rule {rule.audit_id}")
        if not reviewer or not reviewed_at:
            raise ManualReviewValidationError(
                f"reviewer and reviewed_at required for rule {rule.audit_id}")
        outcomes[rule.audit_id] = ManualReviewOutcome(
            rule.audit_id, status, _field(block, "URL/entity") or "SITE",
            evidence, notes, reviewer, reviewed_at)
    return outcomes


def findings_from_manual_outcomes(outcomes: dict[int, ManualReviewOutcome],
                                  registry: list[RuleDefinition]) -> list[Finding]:
    """Convert issue outcomes to findings while preserving PASS/N/A separately."""
    by_id = {rule.audit_id: rule for rule in _manual_rules(registry)}
    findings = []
    for audit_id in sorted(outcomes):
        outcome = outcomes[audit_id]
        if outcome.status not in {"WARNING", "FAIL"}:
            continue
        rule = by_id[audit_id]
        findings.append(Finding(
            audit_id=audit_id, rule_id=rule.rule_id, url=outcome.entity,
            category=rule.category.value, priority=rule.priority.value,
            severity="Warning" if outcome.status == "WARNING" else rule.severity.value,
            finding_type=rule.default_finding_type, scope=rule.scope.value,
            detected_value=f"Manual review result: {outcome.status}",
            expected_value=rule.acceptance_criteria, evidence=outcome.evidence,
            finding_detail=outcome.notes or outcome.evidence,
            remediation=rule.remediation, owner=rule.owner,
            acceptance_criteria=rule.acceptance_criteria,
            data_source="Manual Review", confidence=1.0))
    return findings


def parse_manual_review(markdown: str, registry: list[RuleDefinition], *,
                        expected_site: str = "") -> list[Finding]:
    """Compatibility wrapper converting completed review issues to findings."""
    return findings_from_manual_outcomes(
        parse_manual_review_outcomes(markdown, registry, expected_site=expected_site),
        registry)
