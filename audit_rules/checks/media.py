"""Phase 2 — Local Check Implementation for Media & Rich Media Rules.

Rule 79: Image ALT / Link Quality (check_image_alt_quality)

Pure functions using existing LibreCrawl export data only.
No HTTP requests, no external APIs.
"""

from __future__ import annotations

import re
import logging
from collections import Counter
from urllib.parse import urlparse

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
# Pattern matchers for alt-text analysis
# ---------------------------------------------------------------------------

# Matches filenames commonly used as alt text (e.g., "image.jpg", "photo-123.png")
_FILENAME_ALT_RE = re.compile(
    r"^(?:img|image|photo|pic|picture|screenshot|screen|graphic|logo|banner"
    r"|icon|avatar|thumb|bg|header|footer|button)[-_]?\d*"
    r"\.(?:jpg|jpeg|png|gif|webp|svg|bmp|tiff?|ico)$",
    re.IGNORECASE,
)

# Matches codes like "SPX-0045" that are not meaningful alt
_MEANINGLESS_CODE_RE = re.compile(r"^[A-Z]{2,4}[-_]\d{2,6}$")

# Recognised placeholder / "not a real alt" values
_PLACEHOLDER_ALTS: set[str] = {
    "", "n/a", "na", "none", "null", "undefined", "img", "image",
    "picture", "photo", "spacer", "blank",
}

# Valid decorative alt (intentionally empty) — never flagged
_DECORATIVE_ALT = ""

# Maximum reasonable alt text length before it's considered keyword-stuffed
_MAX_ALT_LENGTH = 125

# Minimum meaningful alt text length
_MIN_MEANINGFUL_ALT_LENGTH = 4

# Threshold for repeated identical alt across unrelated images
_REPEATED_ALT_THRESHOLD = 5

# Keyword-stuffing detection: number of comma-separated tokens to trigger
_KEYWORD_STUFFING_TOKEN_THRESHOLD = 5


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _is_filename_like(alt: str) -> bool:
    """Return True if the alt text looks like a filename rather than a description."""
    return bool(_FILENAME_ALT_RE.match(alt.strip()))


def _is_meaningless_code(alt: str) -> bool:
    """Return True if alt looks like a SKU/code (e.g., 'ABC-1234')."""
    return bool(_MEANINGLESS_CODE_RE.match(alt.strip()))


def _is_placeholder(alt: str) -> bool:
    """Return True if alt text is a known placeholder/non-descriptive value."""
    return alt.strip().lower() in _PLACEHOLDER_ALTS


def _count_comma_keywords(alt: str) -> int:
    """Count the number of comma (or Chinese comma) separated tokens in alt text.

    A high count may indicate keyword stuffing.
    """
    # Split on commas or Chinese commas
    tokens = re.split(r"[,，]", alt)
    # Filter out empty tokens
    meaningful = [t.strip() for t in tokens if t.strip()]
    return len(meaningful)


def _normalize_alt(alt: str) -> str:
    """Normalize alt text for comparison: lowercase, collapsed whitespace."""
    return " ".join(alt.lower().split())


# ---------------------------------------------------------------------------
# Rule 79 — Image ALT / Link Quality
# ---------------------------------------------------------------------------

def check_image_alt_quality(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 79: Image ALT / Link Quality.

    For each 200-status page, analyze its images for alt-text quality issues:
      1. Very short meaningless alt (1-3 chars, not N/A-like) -> WARNING
      2. Very long alt (>125 chars) -> INFO (never FAIL)
      3. Filename-only alt -> WARNING
      4. Repeated identical alt across >=5 unrelated images -> OPPORTUNITY
      5. Possible keyword stuffing (5+ comma-separated tokens) -> INFO
      6. Linked image with empty accessible name -> WARNING
      7. Decorative images (alt="") -> intentionally valid, never flagged
      8. Missing alt already covered, but flag if missing_alt > 0 -> WARNING

    Group findings per-page with specific image src URLs in evidence.

    Args:
        rule: RuleDefinition for this check.
        site_ctx: Site-level context.
        page_contexts: All page contexts from the crawl.
        data: Additional data dict (unused here).

    Returns:
        List of Finding objects.
    """
    findings: list[Finding] = []

    for ctx in page_contexts:
        if ctx.status_code != 200:
            continue

        url = ctx.url

        # Get raw images list from export
        raw = ctx._raw_export or {}
        images: list[dict] = raw.get("images") or []

        # Get image summary for quick stats
        img_summary = ctx.image_summary or {}
        missing_alt_count = img_summary.get("missing_alt", 0)

        if not images:
            # Still flag missing_alt if summary says so (edge case)
            if missing_alt_count > 0:
                findings.append(_mk(
                    rule=rule,
                    url=url,
                    detected=f"image_summary reports {missing_alt_count} images missing alt",
                    expected="All meaningful images should have descriptive alt text",
                    evidence=f"page={url}, missing_alt_count={missing_alt_count}",
                    detail=(
                        f"Page {url} has {missing_alt_count} images with missing alt text "
                        f"according to image_summary. Full image list unavailable for per-image analysis."
                    ),
                    severity=Severity.WARNING,
                ))
            continue

        # ---- Per-image analysis ----
        per_page_issues: list[dict] = []  # {src, issue_type, alt_preview, detail}

        for img in images:
            src = img.get("src", "") or img.get("url", "")
            alt = img.get("alt", "")
            broken = img.get("broken", False)
            status = img.get("status", 0)
            width = img.get("width", 0)
            height = img.get("height", 0)

            alt_stripped = alt.strip()
            alt_len = len(alt_stripped)

            # Check 7: Decorative images (alt="") — intentionally valid, skip
            if alt_stripped == _DECORATIVE_ALT:
                continue

            # Check 1: Very short but not placeholder-like
            if 1 <= alt_len <= 3 and not _is_placeholder(alt_stripped):
                per_page_issues.append({
                    "src": src,
                    "issue_type": "alt_too_short",
                    "alt_preview": repr(alt_stripped),
                    "detail": f"alt text '{alt_stripped}' is too short to be meaningful",
                })
                continue

            # Check 1b: Meaningless code like SKU/code
            if _is_meaningless_code(alt_stripped):
                per_page_issues.append({
                    "src": src,
                    "issue_type": "alt_meaningless_code",
                    "alt_preview": repr(alt_stripped),
                    "detail": f"alt text '{alt_stripped}' appears to be a non-descriptive code",
                })
                continue

            # Check 2: Very long alt (keyword-stuffed?)
            if alt_len > _MAX_ALT_LENGTH:
                alt_preview = alt_stripped[:80] + "..." if alt_len > 80 else alt_stripped
                per_page_issues.append({
                    "src": src,
                    "issue_type": "alt_too_long",
                    "alt_preview": repr(alt_preview),
                    "detail": f"alt text is {alt_len} chars (max recommended: {_MAX_ALT_LENGTH})",
                })

            # Check 3: Filename-only alt
            if _is_filename_like(alt_stripped):
                per_page_issues.append({
                    "src": src,
                    "issue_type": "alt_is_filename",
                    "alt_preview": repr(alt_stripped),
                    "detail": f"alt text '{alt_stripped}' appears to be a filename, not a description",
                })

            # Check 4: Repeated identical alt — handled cross-image below

            # Check 5: Possible keyword stuffing
            comma_count = _count_comma_keywords(alt_stripped)
            if comma_count >= _KEYWORD_STUFFING_TOKEN_THRESHOLD:
                alt_preview = alt_stripped[:80] + "..." if alt_len > 80 else alt_stripped
                per_page_issues.append({
                    "src": src,
                    "issue_type": "alt_keyword_stuffing",
                    "alt_preview": repr(alt_preview),
                    "detail": (
                        f"alt text contains {comma_count} comma-separated tokens, "
                        f"may indicate keyword stuffing"
                    ),
                })

        # ---- Check 4: Repeated identical alt across images on this page ----
        alt_groups: dict[str, list[str]] = {}
        for img in images:
            alt = (img.get("alt") or "").strip()
            if alt and alt != _DECORATIVE_ALT:
                norm = _normalize_alt(alt)
                alt_groups.setdefault(norm, []).append(img.get("src", "") or img.get("url", ""))

        for norm_alt, srcs in alt_groups.items():
            if len(srcs) >= _REPEATED_ALT_THRESHOLD:
                # Only flag if the alt text itself isn't already flagged as a placeholder/filename
                if not _is_placeholder(norm_alt) and not _is_filename_like(norm_alt):
                    alt_preview = norm_alt[:60] + "..." if len(norm_alt) > 60 else norm_alt
                    per_page_issues.append({
                        "src": ", ".join(srcs[:5]) + (" ..." if len(srcs) > 5 else ""),
                        "issue_type": "alt_repeated_across_images",
                        "alt_preview": repr(alt_preview),
                        "detail": (
                            f"alt text '{alt_preview}' repeated across {len(srcs)} images "
                            f"on this page — may indicate templated defaults"
                        ),
                    })

        # ---- Check 6: Linked image with empty accessible name ----
        # We cannot inspect DOM to see if <img> is inside <a>, but we can
        # check if any image src appears in links_detailed anchor text
        links_detailed = ctx.links_detailed or []
        link_anchors: dict[str, str] = {}
        for link in links_detailed:
            link_url = link.get("url", "") or link.get("href", "")
            anchor = link.get("anchor", "") or link.get("text", "")
            if link_url:
                link_anchors[link_url] = anchor

        for img in images:
            alt = (img.get("alt") or "").strip()
            if alt != _DECORATIVE_ALT:
                continue
            src = img.get("src", "") or img.get("url", "")
            if not src:
                continue

            # Check if the image src appears as an anchor in links
            for link_url, anchor_text in link_anchors.items():
                if src in link_url or link_url in src:
                    if not anchor_text:
                        per_page_issues.append({
                            "src": src,
                            "issue_type": "linked_image_empty_alt",
                            "alt_preview": repr(alt),
                            "detail": (
                                f"Image '{src}' with empty alt appears to be inside a link "
                                f"with no accessible name"
                            ),
                        })
                    break

        # ---- Build findings for this page ----
        for issue in per_page_issues:
            issue_type = issue["issue_type"]

            if issue_type in ("alt_too_short", "alt_meaningless_code", "alt_is_filename",
                              "linked_image_empty_alt"):
                severity = Severity.WARNING
            elif issue_type == "alt_repeated_across_images":
                severity = Severity.OPPORTUNITY
            elif issue_type in ("alt_too_long", "alt_keyword_stuffing"):
                severity = Severity.INFO
            else:
                severity = Severity.INFO

            evidence = (
                f"page={url}, "
                f"issue_type={issue_type}, "
                f"image_src={issue['src']}, "
                f"alt_text={issue['alt_preview']}"
            )

            detail_text = (
                f"Image on {url}: {issue['detail']}. "
                f"Image src: {issue['src']}, alt: {issue['alt_preview']}."
            )

            findings.append(_mk(
                rule=rule,
                url=url,
                detected=issue["detail"],
                expected="All meaningful images should have concise, descriptive alt text",
                evidence=evidence,
                detail=detail_text,
                severity=severity,
            ))

        # ---- Check 8: Flag missing_alt count from summary ----
        if missing_alt_count > 0:
            # Only flag if we haven't already produced individual findings for all of them
            # (summary-level finding)
            findings.append(_mk(
                rule=rule,
                url=url,
                detected=f"{missing_alt_count} images missing alt text (from image_summary)",
                expected="All meaningful images should have descriptive alt text",
                evidence=f"page={url}, missing_alt_count={missing_alt_count}",
                detail=(
                    f"Page {url} has {missing_alt_count} images with missing alt text. "
                    f"Total images on page: {img_summary.get('count', 'unknown')}."
                ),
                severity=Severity.WARNING,
            ))

    return findings
