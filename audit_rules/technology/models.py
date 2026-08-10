"""Technology Intelligence data contracts.

Status semantics:
  DETECTED     — sufficient evidence supports the technology.
  NOT_DETECTED — no supporting evidence observed; this never means the site
                 definitely lacks the technology.
  UNKNOWN      — insufficient data / collection capability / conflict.
  CONFLICTING  — multiple credible mutually-exclusive judgments.

Confidence: client display High/Medium/Low; internal score 0.00–1.00.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Optional


SCHEMA_VERSION = "technology-profile-v1"
DETECTOR_VERSION = "1.1.0"
SIGNATURE_REGISTRY_VERSION = "1.1.0"


def _to_jsonable(value: Any) -> Any:
    """Recursively convert dataclass leaves (evidence) to plain JSON values."""
    if is_dataclass(value) and not isinstance(value, type):
        return _to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def profile_to_jsonable(profile: dict[str, Any]) -> dict[str, Any]:
    """Serialize a TechnologyProfile dict into a fully JSON-safe structure."""
    return _to_jsonable(profile)


class DetectionStatus(str, Enum):
    DETECTED = "DETECTED"
    NOT_DETECTED = "NOT_DETECTED"
    UNKNOWN = "UNKNOWN"
    CONFLICTING = "CONFLICTING"


def status_wording(status: str) -> str:
    """Client-safe wording; NOT_DETECTED never claims definite absence."""
    mapping = {
        "DETECTED": "Detected with sufficient observable evidence.",
        "NOT_DETECTED": (
            "Not detected from the available observable evidence; this does "
            "not prove the technology is absent."
        ),
        "UNKNOWN": (
            "Unknown: cannot be reliably determined from the available "
            "evidence or current collection capability."
        ),
        "CONFLICTING": (
            "Multiple credible signals conflict; confidence is reduced and "
            "the conflict is reported."
        ),
    }
    return mapping.get(status, "Unknown status.")


@dataclass(frozen=True)
class TechnologyEvidence:
    """One structured detection signal."""

    signal_type: str
    signal_value: str
    source_url: str
    source_scope: str  # single_page | multi_page | site_level
    strength: str      # strong | medium | weak
    provenance: str = "local_crawl"  # local_crawl | external_api
    pattern: str = ""  # registry signature pattern (signal family)


_STRENGTH_SCORE = {"strong": 0.85, "medium": 0.65, "weak": 0.45}


def _evidence_family(signal: TechnologyEvidence) -> str:
    """Identity of an independent signal family.

    Registered signature patterns are the families: every URL/page matching
    the same pattern corroborates one family. Evidence without a pattern
    (e.g., external facts) falls back to its signal type so raw instances
    never fake independent fingerprints.
    """
    return signal.pattern or signal.signal_type


def aggregate_confidence(
    signals: list[TechnologyEvidence],
) -> tuple[float, bool]:
    """Aggregate evidence into (confidence_score, is_conflicting).

    Confidence is based on independent signature families plus bounded source
    breadth. One strong family across many pages stays High (0.80-0.82), never
    0.92; two distinct strong families reach 0.92. Multiple URLs matching the
    same pattern corroborate but are not independent fingerprints.

    CONFLICTING is NOT derived here: it is produced only by the detector from
    genuinely mutually-exclusive technology judgments (credible competing CMS
    candidates, declared negative signals).
    """
    if not signals:
        return 0.0, False
    families: dict[str, list[TechnologyEvidence]] = {}
    for signal in signals:
        families.setdefault(_evidence_family(signal), []).append(signal)
    strong_families = [
        family for family, items in families.items()
        if any(item.strength == "strong" for item in items)
    ]
    if len(strong_families) >= 2:
        return 0.92, False
    if len(strong_families) == 1:
        sources = {signal.source_url for signal in signals
                   if signal.strength == "strong"}
        # Cross-page corroboration of a single strong family adds bounded
        # reliability but must not impersonate independent fingerprints.
        breadth = 0.82 if len(sources) >= 3 else 0.8
        return breadth, False
    scores = [_STRENGTH_SCORE.get(s.strength, 0.4) for s in signals]
    return max(scores) - 0.1, False


def confidence_label(score: float) -> str:
    if score >= 0.8:
        return "High"
    if score >= 0.5:
        return "Medium"
    return "Low"


@dataclass
class TechnologyDetection:
    """One detected (or explicitly not detected) technology."""

    category: str
    technology_name: str
    technology_type: str
    detection_sources: list[TechnologyEvidence]
    status: str = DetectionStatus.DETECTED.value
    version: str = "Unknown"
    confidence: str = "Low"
    confidence_score: float = 0.0
    base_confidence_score: float = 0.0
    first_seen_urls: list[str] = field(default_factory=list)
    affected_urls: list[str] = field(default_factory=list)
    is_observation: bool = True
    is_risk: bool = False
    risk_level: Optional[str] = None
    risk_reason: str = ""
    mapped_audit_ids: list[int] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    external_enrichment: dict[str, Any] = field(default_factory=dict)
    conflicting_signals: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.detection_sources:
            raise ValueError("technology detection requires evidence")
        if not self.confidence_score:
            score, _ = aggregate_confidence(self.detection_sources)
            self.base_confidence_score = round(score, 2)
            self.confidence_score = self.base_confidence_score
            self.confidence = confidence_label(self.confidence_score)
        else:
            self.base_confidence_score = (
                self.base_confidence_score or self.confidence_score)


@dataclass
class TechnologyProfile:
    """Site-level technology profile."""

    schema_version: str = SCHEMA_VERSION
    detector_version: str = DETECTOR_VERSION
    signature_registry_version: str = SIGNATURE_REGISTRY_VERSION
    source_url: str = ""
    generated_at: str = ""
    git_head: str = ""
    detections: list[TechnologyDetection] = field(default_factory=list)
    detection_status: str = "COMPLETE"
    detection_reason: str = ""
    limitations: list[str] = field(default_factory=list)
    external_enrichment: dict[str, Any] = field(default_factory=dict)

    @property
    def category_summary(self) -> dict[str, list[str]]:
        summary: dict[str, list[str]] = {}
        for detection in self.detections:
            if detection.status == DetectionStatus.DETECTED.value:
                summary.setdefault(detection.category, []).append(
                    detection.technology_name)
        return summary


@dataclass
class TechnologyRisk:
    """Correlation of a confirmed observation to existing audits."""

    technology: str
    observation: TechnologyDetection
    classification: str  # CONFIRMED_OBSERVATION | RISK_CANDIDATE | NO_RISK
    mapped_audit_ids: list[int] = field(default_factory=list)
    impact: str = ""
    recommended_action: str = ""


def build_profile(
    detections: list[TechnologyDetection],
    *,
    detector_version: str,
    signature_registry_version: str,
    source_url: str,
    git_head: str,
    generated_at: str = "",
    detection_status: str = "COMPLETE",
    detection_reason: str = "",
    limitations: Optional[list[str]] = None,
    external_enrichment: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build a serializable TechnologyProfile dict."""
    profile = TechnologyProfile(
        detector_version=detector_version,
        signature_registry_version=signature_registry_version,
        source_url=source_url,
        generated_at=generated_at,
        git_head=git_head,
        detections=detections,
        detection_status=detection_status,
        detection_reason=detection_reason,
        limitations=limitations or [],
        external_enrichment=external_enrichment or {},
    )
    return {
        "schema_version": profile.schema_version,
        "detector_version": profile.detector_version,
        "signature_registry_version": profile.signature_registry_version,
        "source_url": profile.source_url,
        "generated_at": profile.generated_at,
        "git_head": profile.git_head,
        "detections": [d.__dict__ for d in profile.detections],
        "category_summary": profile.category_summary,
        "detection_status": profile.detection_status,
        "detection_reason": profile.detection_reason,
        "limitations": profile.limitations,
        "external_enrichment": profile.external_enrichment,
    }
