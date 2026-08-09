"""Deterministic quality score with separate coverage and confidence metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from audit_rules.categories import ExecutionStatus
from audit_rules.models import CoverageRow, Finding


_PRIORITY = {"Critical": 4.0, "High": 3.0, "Medium": 2.0, "Low": 1.0}
_SEVERITY = {"Error": 1.0, "Warning": 0.55, "Opportunity": 0.25, "Info": 0.0}
_EXECUTED = {ExecutionStatus.EXECUTED_FULL.value, ExecutionStatus.EXECUTED_PARTIAL.value}
# Only definitive outcomes participate in the quality score. UNKNOWN rules
# (e.g. #70 accessibility without rendered DOM) express incompleteness
# through Coverage/Confidence instead of earning a PASS score.
_DEFINITIVE_RESULTS = {"PASS", "FAIL", "WARNING", "OPPORTUNITY"}


@dataclass(frozen=True)
class AuditScore:
    overall_score: Optional[float]
    coverage_pct: float
    finding_confidence_pct: Optional[float]
    executed_rules: int
    eligible_rules: int
    category_scores: dict[str, Optional[float]]
    rule_contributions: list[dict]
    excluded_rules: list[int]
    not_checked_rules: list[int]

    def to_dict(self) -> dict:
        return {
            "schema_version": "audit-score-v1",
            "overall_score": self.overall_score,
            "coverage_pct": self.coverage_pct,
            "finding_confidence_pct": self.finding_confidence_pct,
            "confidence": {"pct": self.finding_confidence_pct,
                           "label": _confidence_label(self.finding_confidence_pct)},
            "executed_rules": self.executed_rules,
            "eligible_rules": self.eligible_rules,
            "category_scores": dict(sorted(self.category_scores.items())),
            "rule_contributions": self.rule_contributions,
            "excluded_rules": self.excluded_rules,
            "not_checked_rules": self.not_checked_rules,
            "scoring_version": "1.0",
            "method": {
                "priority_weights": _PRIORITY,
                "severity_factors": _SEVERITY,
                "rule_penalty": "max(priority * severity * confidence) per executed rule",
                "note": "Quality excludes unexecuted rules; coverage is reported separately",
            },
        }


def _confidence_label(value: Optional[float]) -> str:
    if value is None:
        return "Unknown"
    if value >= 80:
        return "High"
    if value >= 50:
        return "Medium"
    return "Low"


def _value(value) -> str:
    return str(value.value) if hasattr(value, "value") else str(value)


def _quality(rows: list[CoverageRow], penalties: dict[int, float]) -> Optional[float]:
    if not rows:
        return None
    denominator = sum(_PRIORITY.get(_value(row.priority), 1.0) for row in rows)
    if denominator <= 0:
        return None
    penalty = sum(min(_PRIORITY.get(_value(row.priority), 1.0),
                      penalties.get(row.audit_id, 0.0)) for row in rows)
    return round(max(0.0, 100.0 * (1.0 - penalty / denominator)), 2)


def compute_audit_score(findings: list[Finding],
                        coverage_rows: list[CoverageRow]) -> AuditScore:
    """Compute quality only from executed rules; expose missing coverage separately."""
    eligible = [row for row in coverage_rows
                if _value(row.execution_status) != ExecutionStatus.NOT_APPLICABLE.value]
    executed = [row for row in eligible if _value(row.execution_status) in _EXECUTED]
    quality_rows = [
        row for row in executed
        if _value(row.result_status) in _DEFINITIVE_RESULTS
    ]
    coverage_pct = round(100.0 * len(executed) / len(eligible), 2) if eligible else 0.0

    penalties: dict[int, float] = {}
    confidence_weight = confidence_total = 0.0
    for finding in findings:
        confidence = max(0.0, min(1.0, float(finding.confidence)))
        priority = _PRIORITY.get(_value(finding.priority), 1.0)
        factor = _SEVERITY.get(_value(finding.severity), 0.0)
        penalties[finding.audit_id] = max(
            penalties.get(finding.audit_id, 0.0), priority * factor * confidence)
        confidence_total += confidence * priority
        confidence_weight += priority

    categories = sorted({row.category for row in quality_rows})
    category_scores = {
        category: _quality([row for row in quality_rows if row.category == category], penalties)
        for category in categories
    }
    finding_confidence = (
        round(100.0 * confidence_total / confidence_weight, 2)
        if confidence_weight else None
    )
    contributions = []
    for row in sorted(quality_rows, key=lambda item: item.audit_id):
        weight = _PRIORITY.get(_value(row.priority), 1.0)
        penalty = min(weight, penalties.get(row.audit_id, 0.0))
        contributions.append({
            "audit_id": row.audit_id, "rule_id": row.rule_id,
            "category": row.category, "weight": weight,
            "penalty": round(penalty, 4),
            "rule_score": round(100.0 * (1.0 - penalty / weight), 2),
        })
    return AuditScore(
        overall_score=_quality(quality_rows, penalties),
        coverage_pct=coverage_pct,
        finding_confidence_pct=finding_confidence,
        executed_rules=len(executed), eligible_rules=len(eligible),
        category_scores=category_scores,
        rule_contributions=contributions,
        excluded_rules=sorted(row.audit_id for row in coverage_rows
                              if _value(row.execution_status) == ExecutionStatus.NOT_APPLICABLE.value),
        not_checked_rules=sorted(row.audit_id for row in coverage_rows
                                 if _value(row.execution_status) == ExecutionStatus.NOT_CHECKED.value),
    )
