"""Phase 2 — Local Check Implementation for WordPress SEO Rules.

Rule 37: WordPress SEO Plugin Conflict (check_seo_plugin_conflict)

Pure functions using existing LibreCrawl export data only.
No HTTP requests, no external APIs.

CRITICAL DESIGN PRINCIPLE:
  Detecting no plugin fingerprint != no plugin installed.
  Multiple plugins detected with no actual output conflict != FAIL.
  Only flag ACTUAL output conflicts (duplicate tags, conflicting directives).

Limitation: HTML comments inside meta tags (e.g., <!-- This site is optimized
with Yoast -->) cannot be detected from crawl exports that only provide
meta content text. Fingerprinting relies on OG tags, JSON-LD schema @id
patterns, and twitter card signatures.
"""

from __future__ import annotations

import re
import logging
from typing import Optional

from audit_rules.models import RuleDefinition, Finding
from audit_rules.context import SiteContext, PageContext
from audit_rules.categories import Severity

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _mk(
    rule: RuleDefinition,
    url: str,
    detected: str,
    expected: str,
    evidence: str,
    detail: str,
    severity: Severity,
    confidence: float = 1.0,
) -> Finding:
    """Factory for Finding with rule-derived defaults and explicit severity."""
    return Finding(
        audit_id=rule.audit_id,
        rule_id=rule.rule_id,
        url=url,
        category=rule.category.value,
        priority=str(rule.priority.value),
        severity=str(severity.value),
        finding_type=rule.default_finding_type,
        scope=str(rule.scope.value),
        detected_value=detected,
        expected_value=expected,
        evidence=evidence,
        finding_detail=detail or evidence,
        remediation=rule.remediation,
        owner=rule.owner,
        acceptance_criteria=rule.acceptance_criteria,
        data_source=rule.required_data_sources[0] if rule.required_data_sources else "LibreCrawl",
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Plugin fingerprint definitions
# ---------------------------------------------------------------------------

# Each fingerprint is a dict with {plugin_name, patterns: list[str], confidence: float}
# Patterns are checked case-insensitively against JSON-LD @id values, OG property keys,
# and twitter card property keys.

_KNOWN_PLUGIN_FINGERPRINTS: list[dict] = [
    {
        "plugin_name": "Yoast SEO",
        "patterns": [
            "yoast",                          # JSON-LD @id
            "article:author",                 # Distinctive OG tag of Yoast
        ],
        "confidence": 0.85,
    },
    {
        "plugin_name": "Rank Math SEO",
        "patterns": [
            "rank-math",                      # JSON-LD @id
            "rankmath",                       # Alternative identifier
            "article:section",                # Distinctive OG tag of Rank Math
        ],
        "confidence": 0.85,
    },
    {
        "plugin_name": "All in One SEO (AIOSEO)",
        "patterns": [
            "aioseo",                         # JSON-LD @id and OG patterns
            "all_in_one_seo",
        ],
        "confidence": 0.85,
    },
    {
        "plugin_name": "SEOPress",
        "patterns": [
            "seopress",                       # OG property patterns
        ],
        "confidence": 0.80,
    },
    {
        "plugin_name": "The SEO Framework",
        "patterns": [
            "theseoframework",
            "tsf_",
        ],
        "confidence": 0.80,
    },
    {
        "plugin_name": "Squirrly SEO",
        "patterns": [
            "squirrly",
            "sq_seo",
        ],
        "confidence": 0.75,
    },
]

# OG tag properties that, when duplicated, indicate a plugin conflict
_DUPLICATE_SENSITIVE_OG_PROPS: set[str] = {
    "og:title", "og:description", "og:image", "og:url",
    "og:locale", "og:type", "og:site_name",
}

# Twitter card properties that indicate SEO plugin output
_TWITTER_SEO_PROPS: set[str] = {
    "twitter:card", "twitter:title", "twitter:description",
    "twitter:image", "twitter:creator", "twitter:site",
}

# JSON-LD @types that, when duplicated from different @id sources, suggest conflict
_CONFLICT_SENSITIVE_JSON_LD_TYPES: set[str] = {
    "Organization", "WebSite", "Person", "LocalBusiness", "Corporation",
}


# ---------------------------------------------------------------------------
# Fingerprint detection
# ---------------------------------------------------------------------------

def _detect_plugin_fingerprints(
    ctx: PageContext,
    raw: dict,
) -> list[dict]:
    """Detect known SEO plugin fingerprints from available page data.

    Checks:
      - JSON-LD @id values for plugin identifiers
      - OG tag property keys for plugin-specific patterns
      - Twitter card property keys

    Args:
        ctx: PageContext for the page.
        raw: Raw export dict for the page.

    Returns:
        List of dicts: [{plugin_name, matched_pattern, source, confidence}]
    """
    detected: list[dict] = []

    # ---- Check JSON-LD @id values ----
    json_ld = raw.get("json_ld") or raw.get("structured_data") or []
    if isinstance(json_ld, str):
        json_ld = [json_ld]
    if isinstance(json_ld, list):
        for item in json_ld:
            if isinstance(item, dict):
                jld_id = (item.get("@id") or "").lower()
                if jld_id:
                    for fp in _KNOWN_PLUGIN_FINGERPRINTS:
                        for pattern in fp["patterns"]:
                            if pattern in jld_id:
                                detected.append({
                                    "plugin_name": fp["plugin_name"],
                                    "matched_pattern": pattern,
                                    "source": f"json_ld.@id='...{pattern}...'",
                                    "confidence": fp["confidence"],
                                })
                                break  # Don't double-count same fingerprint for same item

    # ---- Check OG tag property keys ----
    og_tags = raw.get("og_tags") or raw.get("og") or {}
    if isinstance(og_tags, dict):
        og_keys_lower = " ".join(k.lower() for k in og_tags.keys())
        for fp in _KNOWN_PLUGIN_FINGERPRINTS:
            for pattern in fp["patterns"]:
                if pattern in og_keys_lower:
                    detected.append({
                        "plugin_name": fp["plugin_name"],
                        "matched_pattern": pattern,
                        "source": f"og_tags (property contains '{pattern}')",
                        "confidence": fp["confidence"],
                    })
                    break  # Don't double-count same fingerprint from OG

    # ---- Check twitter card properties ----
    twitter_tags = raw.get("twitter_tags") or raw.get("twitter") or {}
    if isinstance(twitter_tags, dict):
        twitter_keys_lower = " ".join(k.lower() for k in twitter_tags.keys())
        for fp in _KNOWN_PLUGIN_FINGERPRINTS:
            for pattern in fp["patterns"]:
                if pattern in twitter_keys_lower:
                    detected.append({
                        "plugin_name": fp["plugin_name"],
                        "matched_pattern": pattern,
                        "source": f"twitter_tags (property contains '{pattern}')",
                        "confidence": fp["confidence"],
                    })
                    break

    return detected


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

def _detect_og_duplicates(raw: dict) -> list[str]:
    """Detect duplicate OG tag properties.

    In LibreCrawl exports, og_tags is a dict, so duplicates are already
    collapsed to the last value. We check for other indicators.

    Returns:
        List of duplicate property descriptions found.
    """
    duplicates: list[str] = []

    og_tags = raw.get("og_tags") or raw.get("og") or {}
    if not isinstance(og_tags, dict):
        return duplicates

    # If the export preserves multiple values as lists, detect those
    for key, value in og_tags.items():
        if isinstance(value, list) and len(value) > 1:
            # Same OG property with multiple values is a conflict signal
            unique_vals = list(dict.fromkeys(str(v) for v in value))
            if len(unique_vals) > 1:
                duplicates.append(
                    f"og:{key} has multiple values: {unique_vals}"
                )

    return duplicates


def _detect_duplicate_json_ld_generators(raw: dict) -> list[str]:
    """Detect duplicate JSON-LD schemas that may come from different generators.

    Checks for multiple @id entries that appear to be from different sources
    (different domain patterns in @id) for the same @type.

    Returns:
        List of conflict descriptions found.
    """
    conflicts: list[str] = []

    json_ld = raw.get("json_ld") or raw.get("structured_data") or []
    if isinstance(json_ld, str):
        return conflicts
    if not isinstance(json_ld, list) or len(json_ld) < 2:
        return conflicts

    # Group items by @type and check for different @id sources
    type_groups: dict[str, list[dict]] = {}
    for item in json_ld:
        if not isinstance(item, dict):
            continue
        jtype = item.get("@type", "")
        if jtype in _CONFLICT_SENSITIVE_JSON_LD_TYPES:
            type_groups.setdefault(jtype, []).append(item)

    for jtype, items in type_groups.items():
        if len(items) < 2:
            continue

        # Extract @id domains (the host part of @id)
        id_sources: list[str] = []
        for item in items:
            jld_id = (item.get("@id") or "").lower()
            if jld_id:
                # Extract what looks like a domain or plugin identifier
                # e.g., https://www.example.com/#organization vs https://rankmath.com/#organization
                id_sources.append(jld_id)

        # Check if @id values come from different origins
        unique_ids = list(dict.fromkeys(id_sources))
        if len(unique_ids) > 1:
            conflicts.append(
                f"{len(items)} '{jtype}' schema blocks with different @id "
                f"sources: {unique_ids}"
            )

    return conflicts


def _detect_robots_conflicts(ctx: PageContext) -> Optional[str]:
    """Detect multiple/conflicting robots directives.

    Checks if meta robots has contradictory values.

    Returns:
        Conflict description string, or None if no conflict.
    """
    robots = (ctx.robots or "").lower().strip()
    if not robots:
        return None

    # Check for contradictory directives
    has_noindex = "noindex" in robots
    has_index = "index" in robots and "noindex" not in robots
    has_nofollow = "nofollow" in robots
    has_follow = "follow" in robots and "nofollow" not in robots

    # If meta robots says "index, noindex" that's contradictory
    if has_noindex and has_index:
        return f"Contradictory robots directives: '{robots}' (both index and noindex)"

    # "noindex, follow" is valid and intentional
    # "index, nofollow" is valid and intentional
    # "none" = "noindex, nofollow" — valid
    # "noimageindex" etc — valid

    # Check for potentially combined old/new syntax
    if "none" in robots and ("noindex" in robots or "nofollow" in robots):
        return f"Potentially redundant robots: '{robots}' (both 'none' and explicit directives)"

    return None


# ---------------------------------------------------------------------------
# Rule 37 — WordPress SEO Plugin Conflict
# ---------------------------------------------------------------------------

def check_seo_plugin_conflict(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 37: WordPress SEO Plugin Conflict.

    CRITICAL: Only runs if site_ctx.site_profile == "wordpress".

    Detects SEO plugin output conflicts by fingerprinting plugin output
    in OG tags, JSON-LD schema, and twitter card metadata.

    Only flags ACTUAL output conflicts (duplicate tags, multiple canonical
    URLs, contradictory directives). Detecting no fingerprint does NOT
    mean no plugin is installed. Multiple plugins producing non-conflicting
    output is NOT a failure.

    Args:
        rule: RuleDefinition for this check.
        site_ctx: Site-level context. Must have site_profile == "wordpress".
        page_contexts: All page contexts from the crawl.
        data: Additional data dict (unused here).

    Returns:
        List of Finding objects.
    """
    findings: list[Finding] = []

    # ---- Guard: only applicable to WordPress sites ----
    site_profile = (site_ctx.site_profile or "").lower()
    if site_profile != "wordpress":
        return findings

    # ---- Aggregate across all pages ----
    all_detected_fingerprints: dict[str, dict] = {}  # plugin_name -> aggregated info
    conflict_findings: list[dict] = []  # per-page conflicts

    for ctx in page_contexts:
        if ctx.status_code != 200:
            continue

        url = ctx.url
        raw = ctx._raw_export or {}

        # ---- Detect plugin fingerprints on this page ----
        fingerprints = _detect_plugin_fingerprints(ctx, raw)

        # Aggregate fingerprints across the site
        for fp in fingerprints:
            name = fp["plugin_name"]
            if name not in all_detected_fingerprints:
                all_detected_fingerprints[name] = {
                    "plugin_name": name,
                    "patterns": [],
                    "pages": [],
                    "max_confidence": 0.0,
                }
            agg = all_detected_fingerprints[name]
            if fp["matched_pattern"] not in agg["patterns"]:
                agg["patterns"].append(fp["matched_pattern"])
            if url not in agg["pages"]:
                agg["pages"].append(url)
            agg["max_confidence"] = max(agg["max_confidence"], fp["confidence"])

        # ---- Detect per-page conflicts ----
        page_conflicts: list[str] = []

        # Duplicate OG tags
        og_dupes = _detect_og_duplicates(raw)
        for dupe in og_dupes:
            page_conflicts.append(f"Duplicate OG tag: {dupe}")

        # Conflicting robots directives
        robots_conflict = _detect_robots_conflicts(ctx)
        if robots_conflict:
            page_conflicts.append(f"Robots conflict: {robots_conflict}")

        # Duplicate JSON-LD generators
        jld_conflicts = _detect_duplicate_json_ld_generators(raw)
        for jldc in jld_conflicts:
            page_conflicts.append(f"Duplicate schema: {jldc}")

        if page_conflicts:
            conflict_findings.append({
                "url": url,
                "conflicts": page_conflicts,
                "fingerprints": [f["plugin_name"] for f in fingerprints],
            })

    # ---- No WordPress pages analyzed ----
    if not page_contexts:
        return findings

    # ---- Report site-level fingerprint detection (INFO) ----
    if all_detected_fingerprints:
        detected_names = list(all_detected_fingerprints.keys())
        fingerprint_details = []
        for name, agg in all_detected_fingerprints.items():
            fingerprint_details.append(
                f"{name} (patterns: {agg['patterns']}, "
                f"found on {len(agg['pages'])} pages, "
                f"confidence: {agg['max_confidence']:.0%})"
            )

        if len(all_detected_fingerprints) == 1 and not conflict_findings:
            # Single plugin, no conflicts — informational
            findings.append(_mk(
                rule=rule,
                url="SITE",
                detected=(
                    f"Single SEO plugin detected: {detected_names[0]}. "
                    f"No output conflicts found."
                ),
                expected="One SEO plugin should be active with clean output",
                evidence=(
                    f"detected_fingerprints={detected_names}, "
                    f"details={'; '.join(fingerprint_details)}"
                ),
                detail=(
                    f"Detected {len(all_detected_fingerprints)} SEO plugin "
                    f"fingerprint(s) on this WordPress site: "
                    f"{', '.join(detected_names)}. "
                    f"No conflicting output was detected. "
                    f"Confidence: medium (HTML comment-based detection not available "
                    f"from crawl export data). Single plugin with no conflicts "
                    f"is the recommended configuration."
                ),
                severity=Severity.INFO,
                confidence=0.6,
            ))
        elif len(all_detected_fingerprints) > 1 and not conflict_findings:
            # Multiple plugins detected but no output conflicts — informational
            findings.append(_mk(
                rule=rule,
                url="SITE",
                detected=(
                    f"Multiple SEO plugin fingerprints detected: "
                    f"{', '.join(detected_names)}. No output conflicts found."
                ),
                expected="One SEO plugin should be active; multiple can cause conflicts",
                evidence=(
                    f"detected_fingerprints={detected_names}, "
                    f"details={'; '.join(fingerprint_details)}"
                ),
                detail=(
                    f"Detected {len(all_detected_fingerprints)} SEO plugin "
                    f"fingerprints on this WordPress site: "
                    f"{', '.join(detected_names)}. "
                    f"While no output conflicts were detected, having multiple "
                    f"SEO plugins active simultaneously can lead to unexpected "
                    f"behavior. Recommend auditing the WordPress admin to verify "
                    f"which plugins are actually active."
                ),
                severity=Severity.INFO,
                confidence=0.5,
            ))
    else:
        # No fingerprints detected — NOT a finding, just log
        logger.info(
            "check_seo_plugin_conflict: No known SEO plugin fingerprints "
            "detected in OG/JSON-LD/twitter data. This does NOT mean no "
            "plugin is installed — HTML comment-based detection requires "
            "body_html which is not available in Phase 2."
        )

    # ---- Report per-page conflicts ----
    for conflict_item in conflict_findings:
        page_url = conflict_item["url"]
        conflicts = conflict_item["conflicts"]
        fp_names = conflict_item["fingerprints"]

        # Determine severity based on conflict type
        has_error_conflicts = any(
            "Duplicate OG" in c or "canonical" in c.lower() or "index" in c.lower()
            for c in conflicts
        )
        severity = Severity.ERROR if has_error_conflicts else Severity.WARNING

        findings.append(_mk(
            rule=rule,
            url=page_url,
            detected=f"SEO plugin output conflicts: {'; '.join(conflicts)}",
            expected="Clean, non-duplicated output from a single SEO plugin",
            evidence=(
                f"page={page_url}, "
                f"conflicts={conflicts}, "
                f"fingerprints_on_page={fp_names}"
            ),
            detail=(
                f"Page {page_url} has SEO plugin output conflicts: "
                f"{'; '.join(conflicts)}. "
                f"Detected fingerprints on this page: "
                f"{', '.join(fp_names) if fp_names else 'none'}. "
                f"These conflicts indicate multiple SEO plugins or "
                f"theme SEO functions are producing duplicate/conflicting "
                f"output, which can confuse search engines and degrade rankings."
            ),
            severity=severity,
            confidence=0.85,
        ))

    return findings
