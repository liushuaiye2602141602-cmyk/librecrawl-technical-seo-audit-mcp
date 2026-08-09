"""Phase 2 — Local Check Implementations for Content & Metadata Rules.

Rule 16: Thin Content (compound judgment, NOT single-threshold)
Rule 17: Near-Duplicate Content (metadata-based fuzzy matching)

Pure functions using existing LibreCrawl export data only.
No HTTP requests, no external APIs.
"""

from __future__ import annotations

import re
import logging
from difflib import SequenceMatcher
from typing import Optional
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
# Rule 16 — Thin Content (compound judgment)
# ---------------------------------------------------------------------------

# URL patterns for heuristic page-type detection
_PAGE_TYPE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("category", re.compile(r"/category/", re.IGNORECASE)),
    ("tag", re.compile(r"/tag/", re.IGNORECASE)),
    ("pagination", re.compile(r"/page/\d+", re.IGNORECASE)),
    ("author", re.compile(r"/author/", re.IGNORECASE)),
    ("contact", re.compile(r"/(contact|about|team)(/|\.|$)", re.IGNORECASE)),
    ("legal", re.compile(r"/(privacy|terms|policy|legal)(/|\.|$)", re.IGNORECASE)),
    ("product", re.compile(r"/(product|shop|item)/", re.IGNORECASE)),
    ("post", re.compile(r"/(blog|news|article)/", re.IGNORECASE)),
    ("post_date", re.compile(r"/\d{4}/\d{1,2}/", re.IGNORECASE)),
]

# Page types that are naturally thin (get a risk reduction)
_NATURALLY_THIN_TYPES: set[str] = {"category", "tag", "pagination", "author", "contact", "legal"}

# Page types where thin content is a stronger signal
_CONTENT_EXPECTED_TYPES: set[str] = {"post", "post_date", "product"}


def _detect_page_type(url: str) -> str:
    """Heuristic page-type detection from URL path.

    Returns the first matching type, or "generic" if no pattern matches.
    """
    if not url:
        return "generic"
    parsed = urlparse(url)
    path = parsed.path or ""
    for ptype, pattern in _PAGE_TYPE_PATTERNS:
        if pattern.search(path):
            return ptype
    return "generic"


def _score_thin_content(
    word_count: int,
    title_len: int,
    meta_len: int,
    h1_len: int,
    page_type: str,
) -> tuple[int, dict]:
    """Compute compound thin-content risk score (0-100).

    Returns (risk_score, breakdown_dict).
    """
    score = 0
    breakdown: dict[str, int] = {}

    # Word count scoring
    if word_count < 100:
        score += 35
        breakdown["word_count_lt_100"] = 35
    elif word_count < 200:
        score += 20
        breakdown["word_count_lt_200"] = 20
    elif word_count < 400:
        score += 10
        breakdown["word_count_lt_400"] = 10

    # Title scoring
    if title_len == 0 or title_len < 10:
        score += 15
        breakdown["title_short_or_missing"] = 15

    # Meta description scoring
    if meta_len == 0 or meta_len < 20:
        score += 15
        breakdown["meta_short_or_missing"] = 15

    # H1 scoring
    if h1_len == 0 or h1_len < 5:
        score += 10
        breakdown["h1_short_or_missing"] = 10

    # Combined penalty: all three metadata fields are short/missing
    title_short = title_len < 10
    meta_short = meta_len < 20
    h1_short = h1_len < 5
    if title_short and meta_short and h1_short:
        score += 10
        breakdown["all_metadata_short"] = 10

    # Naturally thin page types get a risk reduction
    if page_type in _NATURALLY_THIN_TYPES:
        score -= 25
        breakdown["naturally_thin_adj"] = -25

    # Content-expected page types get a penalty for being thin
    if page_type in _CONTENT_EXPECTED_TYPES and word_count < 300:
        score += 10
        breakdown["content_expected_penalty"] = 10

    # Clamp to 0-100
    score = max(0, min(100, score))
    return score, breakdown


def check_thin_content(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 16: Thin Content — compound judgment.

    Evaluates each 200-status page against multiple signals (word count,
    title length, meta description length, H1 length, page type) and
    produces a risk score. Only pages with risk_score >= 40 are flagged.

    Args:
        rule: RuleDefinition for this check.
        site_ctx: Site-level context (unused here but part of the contract).
        page_contexts: All page contexts from the crawl.
        data: Additional data dict (unused here).

    Returns:
        List of Finding objects for thin-content pages.
    """
    findings: list[Finding] = []

    for ctx in page_contexts:
        if ctx.status_code != 200:
            continue

        url = ctx.url
        word_count = ctx.word_count or 0
        title = ctx.title or ""
        meta_desc = ctx.meta_description or ""
        h1 = ctx.h1 or ""

        title_len = len(title.strip())
        meta_len = len(meta_desc.strip())
        h1_len = len(h1.strip())

        page_type = _detect_page_type(url)
        risk_score, breakdown = _score_thin_content(
            word_count, title_len, meta_len, h1_len, page_type
        )

        if risk_score < 40:
            continue

        # Determine severity from risk score
        if risk_score >= 70:
            severity = Severity.WARNING
        elif risk_score >= 50:
            severity = Severity.OPPORTUNITY
        else:
            severity = Severity.INFO

        # Build breakdown string for evidence
        breakdown_parts = []
        for key, val in sorted(breakdown.items()):
            breakdown_parts.append(f"{key}={val:+d}")
        breakdown_str = ", ".join(breakdown_parts)

        evidence = (
            f"word_count={word_count}, "
            f"title_length={title_len}, "
            f"meta_length={meta_len}, "
            f"h1_length={h1_len}, "
            f"detected_page_type={page_type}, "
            f"risk_score={risk_score}, "
            f"breakdown=[{breakdown_str}]"
        )

        detail = (
            f"Thin content risk score {risk_score}/100 ({severity.value}) "
            f"on {url}. "
            f"Word count: {word_count}, title: {title_len} chars, "
            f"meta description: {meta_len} chars, H1: {h1_len} chars, "
            f"page type: {page_type}. "
            f"Factors: {breakdown_str}."
        )

        findings.append(_mk(
            rule=rule,
            url=url,
            detected=f"Risk score {risk_score}/100 (page_type={page_type})",
            expected="Substantial, unique content with adequate metadata",
            evidence=evidence,
            detail=detail,
            severity=severity,
        ))

    return findings


# ---------------------------------------------------------------------------
# Rule 17 — Near-Duplicate Content (metadata-based fuzzy matching)
# ---------------------------------------------------------------------------

MAX_PAGES_FOR_PAIRWISE = 5000


def _build_fingerprint(ctx: PageContext) -> str:
    """Build a metadata fingerprint string for similarity comparison.

    Uses title, meta_description, h1, and og:title (if available from raw export).

    Args:
        ctx: PageContext for the page.

    Returns:
        Pipe-delimited fingerprint string, lowercased.
    """
    title = (ctx.title or "").strip()
    meta = (ctx.meta_description or "").strip()
    h1 = (ctx.h1 or "").strip()

    # Try to extract og:title from raw export data
    og_title = ""
    raw = getattr(ctx, "_raw_export", None)
    if raw is not None:
        og_tags = raw.get("og_tags") or raw.get("og") or {}
        if isinstance(og_tags, dict):
            og_title = (og_tags.get("title") or og_tags.get("og:title") or "").strip()

    return f"{title}|{meta}|{h1}|{og_title}".lower()


def _common_path_prefix(url1: str, url2: str) -> Optional[str]:
    """Return the common directory prefix of two URLs, or None if no shared directory.

    Used to detect same-template pages (e.g., /products/item-A and /products/item-B).

    Args:
        url1: First URL.
        url2: Second URL.

    Returns:
        Common path prefix up to the last shared '/', or None if only root is shared.
    """
    try:
        p1 = urlparse(url1).path.rstrip("/")
        p2 = urlparse(url2).path.rstrip("/")
    except Exception:
        return None

    # Find the common prefix directory
    # e.g., /products/item-A and /products/item-B → share /products/
    # but /page-A and /page-B → only share / (root) → exclude
    segments1 = p1.split("/")
    segments2 = p2.split("/")

    common_segments = []
    for s1, s2 in zip(segments1, segments2):
        if s1 == s2:
            common_segments.append(s1)
        else:
            break

    # Need at least 2 meaningful segments (e.g., "/products/") to count as same template
    if len(common_segments) >= 2 and common_segments[1]:
        return "/".join(common_segments) + "/"
    return None


def _matched_fields(
    title1: str, title2: str,
    meta1: str, meta2: str,
    h1_1: str, h1_2: str,
    og1: str, og2: str,
    threshold: float,
) -> list[str]:
    """Determine which individual metadata fields are near-duplicate.

    Args:
        title1, title2: Titles from the two pages.
        meta1, meta2: Meta descriptions from the two pages.
        h1_1, h1_2: H1 headings from the two pages.
        og1, og2: OG titles from the two pages.
        threshold: Similarity threshold for a field to be considered matched.

    Returns:
        List of field names that are near-duplicate.
    """
    matched = []
    if title1 and title2 and SequenceMatcher(None, title1.lower(), title2.lower()).ratio() >= threshold:
        matched.append("title")
    if meta1 and meta2 and SequenceMatcher(None, meta1.lower(), meta2.lower()).ratio() >= threshold:
        matched.append("meta_description")
    if h1_1 and h1_2 and SequenceMatcher(None, h1_1.lower(), h1_2.lower()).ratio() >= threshold:
        matched.append("h1")
    if og1 and og2 and SequenceMatcher(None, og1.lower(), og2.lower()).ratio() >= threshold:
        matched.append("og_title")
    return matched


def check_near_duplicate(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 17: Near-Duplicate Content — metadata-based fuzzy matching.

    Compares pages pairwise using SequenceMatcher on metadata fingerprints
    (title, meta_description, h1, og:title). Flags pairs with similarity
    >= SIMILARITY_THRESHOLD (configurable via data["near_dup_threshold"],
    default 0.85).

    Excludes pairs where:
      - Both URLs share the same path prefix (same template).
      - One page's canonical_url points to the other (canonicalized).

    Performance: O(n^2) on metadata strings, capped at MAX_PAGES_FOR_PAIRWISE (5000).

    Args:
        rule: RuleDefinition for this check.
        site_ctx: Site-level context (unused here).
        page_contexts: All page contexts from the crawl (200-status only used).
        data: Additional data dict. May contain "near_dup_threshold" (float, 0.0-1.0).

    Returns:
        List of Finding objects for near-duplicate page pairs.
    """
    threshold = float(data.get("near_dup_threshold", 0.85))
    findings: list[Finding] = []

    # Filter to 200-status pages with at least some metadata
    valid_pages = [
        ctx for ctx in page_contexts
        if ctx.status_code == 200 and (ctx.title or ctx.meta_description or ctx.h1)
    ]

    if len(valid_pages) < 2:
        return findings

    # Cap at MAX_PAGES_FOR_PAIRWISE
    if len(valid_pages) > MAX_PAGES_FOR_PAIRWISE:
        logger.warning(
            "check_near_duplicate: %d pages exceeds max %d; "
            "sampling first %d pages for pairwise comparison.",
            len(valid_pages), MAX_PAGES_FOR_PAIRWISE, MAX_PAGES_FOR_PAIRWISE,
        )
        valid_pages = valid_pages[:MAX_PAGES_FOR_PAIRWISE]

    # Pre-compute fingerprints and metadata for each page
    page_info: list[dict] = []
    for idx, ctx in enumerate(valid_pages):
        fingerprint = _build_fingerprint(ctx)
        if not fingerprint or fingerprint == "|||":
            continue  # Skip pages with zero metadata
        raw = getattr(ctx, "_raw_export", None)
        og_title = ""
        if raw is not None:
            og_tags = raw.get("og_tags") or raw.get("og") or {}
            if isinstance(og_tags, dict):
                og_title = (og_tags.get("title") or og_tags.get("og:title") or "").strip()

        page_info.append({
            "idx": idx,
            "ctx": ctx,
            "fingerprint": fingerprint,
            "title": (ctx.title or "").strip(),
            "meta": (ctx.meta_description or "").strip(),
            "h1": (ctx.h1 or "").strip(),
            "og_title": og_title,
            "url": ctx.url,
            "depth": ctx.depth,
            "canonical": (ctx.canonical_url or "").strip(),
        })

    n = len(page_info)
    # Track which pages have already been flagged as duplicates
    flagged_indices: set[int] = set()

    for i in range(n):
        if i in flagged_indices:
            continue
        pi = page_info[i]

        for j in range(i + 1, n):
            if j in flagged_indices:
                continue
            pj = page_info[j]

            # Exclusion: same path prefix (same template, different items)
            common_prefix = _common_path_prefix(pi["url"], pj["url"])
            if common_prefix is not None:
                continue

            # Exclusion: canonicalized relationship
            if pi["canonical"] and pi["canonical"] == pj["url"]:
                continue
            if pj["canonical"] and pj["canonical"] == pi["url"]:
                continue

            # Compute similarity on full fingerprint
            similarity = SequenceMatcher(None, pi["fingerprint"], pj["fingerprint"]).ratio()

            if similarity < threshold:
                continue

            # Determine which page is the "duplicate" (higher depth, tiebreak by higher index)
            # The "original" is the page with lower depth (or lower index as tiebreaker)
            if pi["depth"] < pj["depth"]:
                original_info, dup_info = pi, pj
            elif pj["depth"] < pi["depth"]:
                original_info, dup_info = pj, pi
            elif i < j:
                original_info, dup_info = pi, pj
            else:
                original_info, dup_info = pj, pi

            # Determine which individual fields matched
            matched = _matched_fields(
                original_info["title"], dup_info["title"],
                original_info["meta"], dup_info["meta"],
                original_info["h1"], dup_info["h1"],
                original_info["og_title"], dup_info["og_title"],
                threshold,
            )

            # Severity from similarity
            if similarity >= 0.95:
                severity = Severity.WARNING
            else:
                severity = Severity.OPPORTUNITY

            evidence = (
                f"source_url={original_info['url']}, "
                f"duplicate_url={dup_info['url']}, "
                f"similarity={similarity:.3f}, "
                f"matched_fields=[{', '.join(matched) if matched else 'fingerprint'}]"
            )

            detail = (
                f"Near-duplicate content detected: "
                f"{dup_info['url']} is {similarity:.1%} similar to "
                f"{original_info['url']}. "
                f"Matched fields: {', '.join(matched) if matched else 'overall fingerprint'}. "
                f"Threshold: {threshold:.0%}."
            )

            findings.append(_mk(
                rule=rule,
                url=dup_info["url"],
                detected=(
                    f"Near-duplicate of {original_info['url']} "
                    f"(similarity={similarity:.3f})"
                ),
                expected="Unique, substantially different content on each page",
                evidence=evidence,
                detail=detail,
                severity=severity,
                confidence=similarity,
            ))

            # Flag the duplicate page so it doesn't become a source in another pair
            flagged_indices.add(dup_info["idx"])

    return findings
