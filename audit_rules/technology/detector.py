"""LocalTechnologyDetector — deterministic, evidence-first detection."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from audit_rules.context import PageContext, SiteContext
from audit_rules.technology.models import (
    DETECTOR_VERSION,
    SCHEMA_VERSION,
    SIGNATURE_REGISTRY_VERSION,
    DetectionStatus,
    TechnologyDetection,
    TechnologyEvidence,
    aggregate_confidence,
    build_profile,
    confidence_label,
)
from audit_rules.technology.signatures import TechnologySignatureRegistry


# Technologies that cannot credibly coexist within one site.
_MUTUALLY_EXCLUSIVE = {"CMS", "Ecommerce"}
_CREDIBLE_CONFLICT_THRESHOLD = 0.5


class LocalTechnologyDetector:
    """Runs the signature registry over PageContext evidence."""

    def __init__(
        self,
        registry: TechnologySignatureRegistry,
        *,
        source_url: str,
        git_head: str,
        detector_version: str = DETECTOR_VERSION,
        signature_registry_version: str = SIGNATURE_REGISTRY_VERSION,
    ):
        self._registry = registry
        self._source_url = source_url
        self._git_head = git_head
        self._detector_version = detector_version
        self._signature_registry_version = signature_registry_version

    def detect(
        self,
        pages: list[PageContext],
        site_ctx: Optional[SiteContext] = None,
    ) -> dict[str, Any]:
        """Return a serializable TechnologyProfile dict."""
        try:
            corpora = [self._build_corpus(page) for page in pages]
            detections: list[TechnologyDetection] = []
            for signature in self._registry.iter_signatures():
                matched = self._match_signature(signature, pages, corpora)
                if not matched:
                    continue
                score, _ = aggregate_confidence(matched)
                version = self._extract_version(signature, matched)
                detection = TechnologyDetection(
                    category=signature.category,
                    technology_name=signature.technology,
                    technology_type=signature.technology_type,
                    detection_sources=matched,
                    version=version,
                    confidence_score=round(score, 2),
                    confidence=confidence_label(score),
                    first_seen_urls=list(dict.fromkeys(
                        e.source_url for e in matched)),
                    affected_urls=list(dict.fromkeys(
                        e.source_url for e in matched)),
                )
                # Claim precision: Medium evidence confirms DETECTED only for
                # vendor-specific signatures declared medium_confirms; generic
                # paths (e.g. WooCommerce /product/) stay an UNKNOWN
                # observation with the evidence preserved.
                if (detection.confidence_score < 0.8
                        and not signature.medium_confirms):
                    detection.status = DetectionStatus.UNKNOWN.value
                detections.append(detection)
            self._apply_negative_signal_conflicts(detections, pages, corpora)
            self._apply_cross_category_conflicts(detections)
            not_detected = self._not_detected_technologies(detections)
            profile = build_profile(
                detections,
                detector_version=self._detector_version,
                signature_registry_version=self._signature_registry_version,
                source_url=self._source_url,
                git_head=self._git_head,
                generated_at=datetime.now(timezone.utc).isoformat().replace(
                    "+00:00", "Z"),
            )
            profile["not_detected_technologies"] = not_detected
            return profile
        except Exception as exc:  # detector failure must never fail the audit
            profile = build_profile(
                [],
                detector_version=self._detector_version,
                signature_registry_version=self._signature_registry_version,
                source_url=self._source_url,
                git_head=self._git_head,
                generated_at=datetime.now(timezone.utc).isoformat().replace(
                    "+00:00", "Z"),
                detection_status="DETECTION_INCOMPLETE",
                detection_reason=str(exc),
            )
            profile["not_detected_technologies"] = []
            return profile

    @staticmethod
    def _build_corpus(page: PageContext) -> dict[str, list[str]]:
        asset_paths = [page.url or ""]
        for link in (page.links_detailed or []):
            if isinstance(link, dict):
                target = (link.get("url") or link.get("href")
                          or link.get("target_url") or "")
                if target:
                    asset_paths.append(str(target))
        for image in (page._raw_export or {}).get("images") or []:
            if isinstance(image, dict):
                src = image.get("src") or image.get("url") or ""
                if src:
                    asset_paths.append(str(src))
        asset_paths.extend(page.scripts or [])
        asset_paths.extend(page.stylesheets or [])
        analytics = (page._raw_export or {}).get("analytics") or {}
        analytics_keys = list(analytics.keys()) if isinstance(analytics, dict) else []
        headers = page.allowlisted_headers or {}
        header_lines = [
            name for name in headers
        ] + [
            f"{name}={value}" for name, value in headers.items()
        ]
        return {
            "meta_generator": [page.meta_generator or ""],
            "script_src": list(page.scripts or []),
            "stylesheet_href": list(page.stylesheets or []),
            "asset_path": asset_paths,
            "url_pattern": [page.url or ""],
            "response_header": header_lines,
            "analytics_fingerprint": analytics_keys,
            "json_ld_type": list(page.json_ld_types or []),
            "robots_meta": [page.robots or ""],
            "cookie_name": [],
        }

    def _match_signature(self, signature, pages, corpora) -> list[TechnologyEvidence]:
        evidence: list[TechnologyEvidence] = []
        for signal in signature.signals:
            signal_type = signal["type"]
            pattern = re.compile(signal["pattern"], re.IGNORECASE)
            for page, corpus in zip(pages, corpora):
                for value in corpus.get(signal_type, []):
                    if not value:
                        continue
                    if pattern.search(str(value)):
                        evidence.append(TechnologyEvidence(
                            signal_type=signal_type,
                            signal_value=str(value)[:200],
                            source_url=page.url or "",
                            source_scope="single_page",
                            strength=signal.get("strength", "weak"),
                            pattern=signal["pattern"],
                        ))
        return evidence

    def _apply_negative_signal_conflicts(
        self, detections, pages, corpora,
    ) -> None:
        """Consume declared negative signals.

        A strong negative signal (a mutually-exclusive alternative, e.g.
        ``meta_generator=Webflow`` against WordPress) matching anywhere in the
        crawl conflicts with a credible positive detection. Weak negatives or
        sub-threshold positives are recorded only as context and never
        downgrade a strong detection.
        """
        signatures = {
            signature.technology: signature
            for signature in self._registry.iter_signatures()
        }
        for detection in detections:
            if detection.status != DetectionStatus.DETECTED.value:
                continue
            signature = signatures.get(detection.technology_name)
            if not signature or not signature.negative_signals:
                continue
            if detection.base_confidence_score < _CREDIBLE_CONFLICT_THRESHOLD:
                continue
            for negative in signature.negative_signals:
                if negative.get("strength") != "strong":
                    continue
                signal_type = negative["type"]
                pattern = re.compile(negative["pattern"], re.IGNORECASE)
                match = self._find_negative_value(corpora, signal_type, pattern)
                if match is None:
                    continue
                detection.status = DetectionStatus.CONFLICTING.value
                detection.confidence_score = round(
                    min(detection.confidence_score, 0.45), 2)
                detection.confidence = confidence_label(
                    detection.confidence_score)
                detection.conflicting_signals.append(
                    f"{signal_type}={str(match)[:80]}")

    @staticmethod
    def _find_negative_value(corpora, signal_type: str, pattern) -> str | None:
        for corpus in corpora:
            for value in corpus.get(signal_type, []):
                if value and pattern.search(str(value)):
                    return str(value)
        return None

    @classmethod
    def _apply_cross_category_conflicts(cls, detections) -> None:
        """Credible mutually-exclusive technologies are CONFLICTING.

        Only members that reached the credible confidence threshold
        participate: a weak competing CMS candidate must not poison a strong
        detection. Sub-threshold members keep their status/confidence.
        """
        for category in _MUTUALLY_EXCLUSIVE:
            members = [
                d for d in detections
                if d.category == category
                and d.status in (
                    DetectionStatus.DETECTED.value,
                    DetectionStatus.CONFLICTING.value,
                )
                and d.base_confidence_score >= _CREDIBLE_CONFLICT_THRESHOLD
            ]
            if len(members) <= 1:
                continue
            for detection in members:
                detection.status = DetectionStatus.CONFLICTING.value
                detection.confidence_score = round(
                    min(detection.confidence_score, 0.45), 2)
                detection.confidence = confidence_label(
                    detection.confidence_score)

    @staticmethod
    def _extract_version(signature, matched) -> str:
        extractor = signature.version_extractor
        if not extractor:
            return "Unknown"
        pattern = re.compile(extractor["pattern"], re.IGNORECASE)
        for evidence in matched:
            match = pattern.search(str(evidence.signal_value))
            if match and match.groups():
                return match.group(1)
        return "Unknown"

    def _not_detected_technologies(self, detections) -> list[str]:
        detected = {d.technology_name for d in detections}
        return [
            s.technology for s in self._registry.iter_signatures()
            if s.technology not in detected
        ]
