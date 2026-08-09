"""Data models for the Unified Audit Rule Registry.

RuleDefinition  — one row from the merged checklist + mapping
Finding         — a single finding produced by evaluating a rule
CoverageRow     — one row in the 80-row coverage matrix
"""

from dataclasses import dataclass, field
from typing import Optional, Callable, Any

from audit_rules.categories import (
    Category, Priority, Severity, Scope,
    ExecutionStatus, ResultStatus, ImplStatus, DetectionMethod,
)


# ============================================================
# RuleDefinition
# ============================================================

@dataclass
class RuleDefinition:
    """One rule from the merged checklist + mapping CSV.

    This is the single source of truth for each of the 80 master audit rules.
    Fields are populated from the CSV files at load time.
    The `rule_function` is bound later during provider setup (Phase 1: adapter only).
    """

    # === Identity (from CSV) ===
    audit_id: int                         # 1–80, matches both CSVs
    rule_id: str                          # Machine-readable, e.g. "robots_txt_exists"
    category: Category                    # Enum
    title: str                            # Chinese title from checklist
    description: str                      # Full description from checklist

    # === Classification ===
    priority: Priority
    severity: Severity                    # Default severity for findings from this rule
    default_finding_type: str             # "Error" / "Warning" / "Opportunity"

    scope: Scope                          # SITE / PAGE / LINK / RELATIONSHIP / TEMPLATE

    # === Execution ===
    execution_type: DetectionMethod       # How the rule detects issues
    required_data_sources: list[str]       # What data providers are needed

    impl_status: ImplStatus               # EXISTING_FULL / EXISTING_PARTIAL / etc.
    automatable: bool                     # Can this rule be automated?

    # === Governance (from CSV) ===
    owner: str                            # SEO / Dev / Content / Infra / Analytics
    remediation: str                      # How to fix (Chinese + English)
    acceptance_criteria: str              # What "pass" looks like
    tools: str                            # Tools that can detect this
    notes: str                            # Caveats, edge cases

    # === Legacy binding (for EXISTING_FULL adapter in Phase 1) ===
    legacy_check_names: list[str] = field(default_factory=list)
    # The executable function (bound later via adapter)
    rule_function: Optional[Callable[..., list["Finding"]]] = None

    @property
    def is_automated(self) -> bool:
        """Can this rule produce findings without human intervention?"""
        return self.impl_status in (
            ImplStatus.EXISTING_FULL,
            ImplStatus.EXISTING_PARTIAL,
            ImplStatus.NEW_AUTO,
        )

    @property
    def is_external(self) -> bool:
        """Does this rule require an external data source?"""
        return self.impl_status == ImplStatus.NEW_EXTERNAL_DATA

    @property
    def is_manual(self) -> bool:
        """Does this rule require human review?"""
        return self.impl_status == ImplStatus.NEW_MANUAL


# ============================================================
# Finding
# ============================================================

@dataclass
class Finding:
    """One finding produced by evaluating a rule against a page/site/link.

    Backward compatible: the legacy fields (url, check_name, severity,
    finding_detail) are preserved for existing CSV exporters.
    New fields are additive only (Requirement 5).
    """

    audit_id: int
    rule_id: str
    url: str                            # Affected URL (or "SITE" for site-level)
    category: str                       # Category label
    priority: str                       # Priority label
    severity: str                       # ERROR / WARNING / OPPORTUNITY / INFO
    finding_type: str                   # Finding type from checklist
    scope: str                          # SITE / PAGE / LINK / RELATIONSHIP / TEMPLATE

    # What was found
    detected_value: str = ""
    expected_value: str = ""
    evidence: str = ""
    finding_detail: str = ""             # LEGACY — maps from extended_checks "detail"

    # Governance
    remediation: str = ""
    owner: str = ""
    acceptance_criteria: str = ""

    # Metadata
    data_source: str = "LibreCrawl"
    confidence: float = 1.0             # 0.0–1.0. <1.0 for heuristics, 1.0 for deterministic

    def to_dict(self) -> dict:
        """Export to dict. Legacy fields preserved for backward compatibility."""
        return {
            "url": self.url,
            "check_name": self.rule_id,        # LEGACY: rule_id used as check_name
            "severity": self.severity,          # LEGACY
            "finding_detail": self.finding_detail,  # LEGACY
            # New fields (additive)
            "audit_id": self.audit_id,
            "rule_id": self.rule_id,
            "category": self.category,
            "priority": self.priority,
            "finding_type": self.finding_type,
            "scope": self.scope,
            "detected_value": self.detected_value,
            "expected_value": self.expected_value,
            "evidence": self.evidence,
            "remediation": self.remediation,
            "owner": self.owner,
            "acceptance_criteria": self.acceptance_criteria,
            "data_source": self.data_source,
            "confidence": self.confidence,
        }


# ============================================================
# CoverageRow
# ============================================================

@dataclass
class CoverageRow:
    """One row in the 80-row coverage matrix (Requirement 0.3, 10).

    Uses the two-axis model:
      - execution_status: WAS the rule executed?
      - result_status:    WHAT was the outcome?
    """

    audit_id: int
    rule_id: str
    category: str
    check: str                           # Title from checklist
    priority: Priority
    scope: Scope
    impl_status: ImplStatus

    execution_status: ExecutionStatus
    result_status: ResultStatus

    eligible_count: int = 0              # How many units are eligible for this rule
    evaluated_count: int = 0             # How many were actually evaluated
    coverage_pct: float = 0.0            # evaluated / eligible * 100
    finding_count: int = 0               # How many findings were produced

    data_source: str = ""
    required_source: str = ""
    not_checked_reason: str = ""         # Why NOT_CHECKED or NOT_APPLICABLE

    owner: str = ""
    remediation: str = ""
    acceptance_criteria: str = ""

    def to_dict(self) -> dict:
        """Export to dict for CSV writing."""
        return {
            "audit_id": self.audit_id,
            "rule_id": self.rule_id,
            "category": self.category,
            "check": self.check,
            "priority": self.priority.value if isinstance(self.priority, Priority) else self.priority,
            "scope": self.scope.value if isinstance(self.scope, Scope) else self.scope,
            "impl_status": self.impl_status.value if isinstance(self.impl_status, ImplStatus) else self.impl_status,
            "execution_status": self.execution_status.value if isinstance(self.execution_status, ExecutionStatus) else self.execution_status,
            "result_status": self.result_status.value if isinstance(self.result_status, ResultStatus) else self.result_status,
            "eligible_count": self.eligible_count,
            "evaluated_count": self.evaluated_count,
            "coverage_pct": f"{self.coverage_pct:.2f}",
            "finding_count": self.finding_count,
            "data_source": self.data_source,
            "required_source": self.required_source,
            "not_checked_reason": self.not_checked_reason,
            "owner": self.owner,
            "remediation": self.remediation,
            "acceptance_criteria": self.acceptance_criteria,
        }
