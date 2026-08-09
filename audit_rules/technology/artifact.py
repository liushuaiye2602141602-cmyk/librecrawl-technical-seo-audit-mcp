"""09_Technology_Profile.json serializer and validator.

The machine artifact is client-safe: it contains only JSON-native values,
structured evidence, versions, provenance, and risk correlations that point
at existing audits #01鈥?80. It never contains raw internal objects,
sensitive headers, cookie values, or debug reprs.
"""

from __future__ import annotations

import json
from typing import Any

from audit_rules.technology.models import (
    DETECTOR_VERSION,
    SCHEMA_VERSION,
    SIGNATURE_REGISTRY_VERSION,
    profile_to_jsonable,
)


TECHNOLOGY_ARTIFACT_KIND = "technology_profile_json"
_REQUIRED_KEYS = frozenset({
    "schema_version", "detector_version", "signature_registry_version",
    "source_url", "detections",
})


def _risk_to_json(risk: Any) -> dict[str, Any]:
    observation = risk.observation
    observation = (
        observation
        if isinstance(observation, dict)
        else getattr(observation, "__dict__", {})
    )
    return {
        "technology": risk.technology,
        "classification": risk.classification,
        "mapped_audit_ids": sorted(int(i) for i in risk.mapped_audit_ids),
        "impact": risk.impact,
        "recommended_action": risk.recommended_action,
        "observation_status": observation.get("status", "UNKNOWN"),
        "observation_confidence": observation.get("confidence", "Low"),
    }


def serialize_technology_artifact(
    profile: dict[str, Any],
    risks: list[Any] | None = None,
) -> dict[str, Any]:
    """Return the client-safe Technology Profile payload as plain JSON data."""
    payload = profile_to_jsonable(dict(profile or {}))
    payload["schema_version"] = payload.get("schema_version") or SCHEMA_VERSION
    payload["detector_version"] = payload.get("detector_version") or DETECTOR_VERSION
    payload["signature_registry_version"] = (
        payload.get("signature_registry_version")
        or SIGNATURE_REGISTRY_VERSION
    )
    payload.setdefault("source_url", "")
    payload.setdefault("git_head", "")
    payload.setdefault("generated_at", "")
    payload.setdefault("detections", [])
    payload.setdefault("detection_status", "COMPLETE")
    payload.setdefault("detection_reason", "")
    payload.setdefault("limitations", [])
    payload.setdefault("category_summary", {})
    payload.setdefault("not_detected_technologies", [])
    payload.setdefault("external_enrichment", {"status": "unavailable"})
    payload["risk_correlations"] = [
        _risk_to_json(risk) for risk in (risks or [])
    ]
    payload["provider_provenance"] = {
        "primary": "local_crawl",
        "external": payload["external_enrichment"],
    }
    validate_technology_artifact(payload)
    return payload


def validate_technology_artifact(payload: dict[str, Any]) -> None:
    """Validate required versions and JSON-native structure; raise on bad data."""
    missing = _REQUIRED_KEYS - payload.keys()
    if missing:
        raise ValueError(
            f"technology artifact missing required keys: "
            f"{sorted(missing)}")
    for key in ("schema_version", "detector_version",
                "signature_registry_version", "source_url"):
        if not isinstance(payload[key], str):
            raise ValueError(f"technology artifact {key} must be a string")
    if not isinstance(payload["detections"], list):
        raise ValueError("technology artifact detections must be a list")
    try:
        text = json.dumps(payload)
    except TypeError as exc:
        raise ValueError(
            "technology artifact contains non-JSON values") from exc
    for marker in ("object at 0x", "<class", "TechnologyEvidence("):
        if marker in text:
            raise ValueError(
                "technology artifact leaks raw internal object reprs")
