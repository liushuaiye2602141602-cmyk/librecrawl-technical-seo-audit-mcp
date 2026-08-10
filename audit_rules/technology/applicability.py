"""CMS applicability bridge: Technology Profile -> site_profile.

Confidence gate:
  High  -> may drive CMS rule applicability.
  Medium -> only when the registry-defined strong-evidence requirement is met.
  Low / CONFLICTING -> observation only; never changes applicability.
"""

from __future__ import annotations

from typing import Any


def cms_applicability_decision(
    profile: dict[str, Any],
    *,
    signature_requirement: str = "STRONG_2",
) -> str:
    """Return 'wordpress_remote' or 'generic' from the profile."""
    wordpress = None
    for detection in profile.get("detections", []):
        if detection.get("technology_name") == "WordPress":
            wordpress = detection
            break
    if not wordpress or wordpress.get("status") != "DETECTED":
        return "generic"
    confidence = wordpress.get("confidence")
    if confidence == "High":
        return "wordpress_remote"
    if confidence == "Medium" and signature_requirement == "STRONG_2":
        families = {
            source.get("pattern") or source.get("signal_type")
            for source in wordpress.get("detection_sources", [])
            if source.get("strength") == "strong"
        }
        strong_count = len(families)
        if strong_count >= 2:
            return "wordpress_remote"
    return "generic"
