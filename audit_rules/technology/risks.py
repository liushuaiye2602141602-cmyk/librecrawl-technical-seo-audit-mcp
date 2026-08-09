"""TechnologyRiskCorrelator.

Three-layer contract:
  1. Technology Observation  — fact, no judgment.
  2. Technology Risk Correlation — metadata mapping to existing audits;
     never a Finding, never a direct score change.
  3. Existing Audit Finding   — produced only by the 80-rule adapters.
"""

from __future__ import annotations

from typing import Any

from audit_rules.technology.models import TechnologyRisk


# v1 mappings: technology -> existing audit ids that consume its evidence.
MAPPINGS: dict[str, tuple[int, ...]] = {
    "WordPress": (36, 37, 38, 39, 64, 65, 66, 67, 68, 69),
    "Cloudflare": (23, 26, 66),
    "Yoast SEO": (37,),
    "Rank Math": (37,),
    "GA4": (34, 35),
    "GTM": (34, 35),
}


class TechnologyRiskCorrelator:
    def __init__(self, mappings: dict[str, tuple[int, ...]] | None = None):
        self._mappings = mappings or MAPPINGS

    def correlate(self, profile: dict[str, Any]) -> list[TechnologyRisk]:
        """Return observations mapped to existing audits (metadata only)."""
        risks: list[TechnologyRisk] = []
        for detection in profile.get("detections", []):
            if detection.get("status") != "DETECTED":
                continue
            name = str(detection.get("technology_name") or "")
            mapped = list(self._mappings.get(name, ()))
            if not mapped:
                continue
            risks.append(TechnologyRisk(
                technology=name,
                observation=detection,
                classification="CONFIRMED_OBSERVATION",
                mapped_audit_ids=mapped,
                impact=self._impact(name, mapped),
            ))
        return risks

    def confirmed_risk(self, risk: TechnologyRisk, coverage_rows) -> bool:
        """True only when a mapped existing audit has a FAIL/WARNING result."""
        by_id = {row.audit_id: row for row in coverage_rows}
        return any(
            by_id.get(audit_id) is not None
            and by_id[audit_id].result_status.value in ("FAIL", "WARNING")
            for audit_id in risk.mapped_audit_ids
        )

    @staticmethod
    def _impact(name: str, mapped: list[int]) -> str:
        audit_list = ", ".join(f"#{audit_id}" for audit_id in mapped)
        return (
            f"Observed {name}; provides evidence/applicability context for "
            f"existing audits {audit_list}. No direct score impact."
        )
