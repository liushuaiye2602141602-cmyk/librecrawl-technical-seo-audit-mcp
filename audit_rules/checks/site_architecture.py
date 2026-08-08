"""Phase 2 Local Checks — Site Architecture (Rules 12, 38, 49, 50).

Pure functions using only existing LibreCrawl export data.
NO HTTP, NO external APIs.

Rule 12 — Pagination / Faceted Navigation   (check_pagination)
Rule 38 — Permalink Structure               (check_permalink)
Rule 49 — URL Normalization                  (check_url_normalization)
Rule 50 — Redirect Relevance (heuristic)     (check_redirect_relevance)
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Optional
from urllib.parse import urlparse, parse_qs

from audit_rules.models import RuleDefinition, Finding
from audit_rules.context import SiteContext, PageContext
from audit_rules.categories import Severity


# ============================================================
# Internal helpers
# ============================================================

def _mk(
    rule: RuleDefinition,
    url: str = "",
    detected: str = "",
    expected: str = "",
    evidence: str = "",
    detail: str = "",
    severity: Severity | str = "",
    confidence: float = 1.0,
) -> Finding:
    """Factory for Finding with rule-derived defaults and optional overrides."""
    sev = severity if severity else rule.severity.value
    if isinstance(sev, Severity):
        sev = sev.value
    return Finding(
        audit_id=rule.audit_id,
        rule_id=rule.rule_id,
        url=url,
        category=rule.category.value if hasattr(rule.category, "value") else str(rule.category),
        priority=str(rule.priority.value) if hasattr(rule.priority, "value") else str(rule.priority),
        severity=str(sev),
        finding_type=rule.default_finding_type,
        scope=str(rule.scope.value) if hasattr(rule.scope, "value") else str(rule.scope),
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


# ============================================================
# Pagination / Faceted URL patterns (Rule 12)
# ============================================================

# Pagination path regex: /2/, /page/2/, /p/2/, /pg/2/, /paged/2
_PAGINATION_PATH_RE = re.compile(
    r"/(?:page|p|pg|paged)/(\d+)/?$"
    r"|/(\d+)/?$"
)

# Pagination query parameter names
_PAGINATION_QUERY_PARAMS = {"page", "p", "pg", "paged"}

# Faceted navigation query parameter names
_FACETED_PARAM_NAMES = {"sort", "filter", "order", "color", "size", "price"}


def _is_pagination_url(url: str) -> bool:
    """Detect pagination URLs by path or query patterns."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"

    # Check path patterns: /page/2/, /p/3, /2/
    if _PAGINATION_PATH_RE.search(path):
        return True

    # Check query patterns: ?page=2, ?p=3, ?pg=4, ?paged=5
    if parsed.query:
        params = parse_qs(parsed.query)
        for param in _PAGINATION_QUERY_PARAMS:
            if param in params:
                return True

    return False


def _is_faceted_url(url: str) -> bool:
    """Detect faceted/filter URLs by query parameters."""
    parsed = urlparse(url)
    if not parsed.query:
        return False

    qs_lower = parsed.query.lower()
    params = parse_qs(parsed.query)

    # Known faceted params
    for param in _FACETED_PARAM_NAMES:
        if f"{param}=" in qs_lower:
            return True

    # 3+ distinct query params suggests faceted navigation
    if len(params) >= 3:
        return True

    return False


def _base_path(url: str) -> str:
    """Extract base path (scheme + netloc + path, no query, no trailing slash)."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


# ============================================================
# Rule 12 — Pagination / Faceted Navigation
# ============================================================

def check_pagination(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Detect pagination and faceted navigation issues.

    Pagination:
      - Non-200 status → WARNING
      - noindex robots → WARNING (pagination should be indexable)
      - Canonical pointing to page/1 or base URL → WARNING
      - Normal self-canonical pagination → no finding

    Faceted navigation:
      - >20 faceted variants of same base path → WARNING (parameter explosion)
      - Self-canonical + indexable faceted URL → OPPORTUNITY (duplicate content risk)
      - Faceted URL canonical pointing to base → expected (no finding)
    """
    findings: list[Finding] = []

    pagination_pages: list[PageContext] = []
    faceted_pages: list[PageContext] = []

    for ctx in page_contexts:
        if _is_pagination_url(ctx.url):
            pagination_pages.append(ctx)
        if _is_faceted_url(ctx.url):
            faceted_pages.append(ctx)

    # ---- Pagination checks ----
    for pctx in pagination_pages:
        # Check status code
        if pctx.status_code != 200:
            findings.append(_mk(
                rule, url=pctx.url,
                detected=f"Status {pctx.status_code}",
                expected="Pagination page returns 200",
                evidence=f"status_code={pctx.status_code}",
                detail=f"Pagination page returns non-200 status: {pctx.url}",
                severity=Severity.WARNING,
            ))
            continue

        # Check noindex — pagination should be indexable for crawl depth
        robots = (pctx.robots or "").lower()
        if "noindex" in robots:
            findings.append(_mk(
                rule, url=pctx.url,
                detected=f"Pagination page has noindex: {pctx.robots}",
                expected="Pagination pages should be indexable (no noindex)",
                evidence=f"robots={pctx.robots}",
                detail=f"Pagination page {pctx.url} has noindex — pagination should be "
                       f"indexable to support crawl depth and discovery",
                severity=Severity.WARNING,
            ))

        # Check self-canonical
        if pctx.canonical_url:
            canon_norm = pctx.canonical_url.rstrip("/")
            url_norm = pctx.url.rstrip("/")

            if canon_norm != url_norm:
                # Detect if canonical is pointing to page/1 or root (first page)
                parsed_canon = urlparse(pctx.canonical_url)
                parsed_self = urlparse(pctx.url)
                canon_path = parsed_canon.path.rstrip("/") or "/"

                # Is canonical pointing to page/1?
                points_to_page1 = bool(
                    re.search(r"/(?:page|p|pg|paged)/1$", canon_path)
                    or canon_path.endswith("/1")
                )
                # Is canonical pointing to base (non-paginated root)?
                canon_is_root = parsed_canon.path in ("", "/")
                self_is_root = parsed_self.path in ("", "/")

                if points_to_page1 or (canon_is_root and not self_is_root):
                    findings.append(_mk(
                        rule, url=pctx.url,
                        detected=f"Canonical points to first page or root: {pctx.canonical_url}",
                        expected="Self-referencing canonical on pagination pages",
                        evidence=f"canonical_url={pctx.canonical_url}",
                        detail=f"Pagination page {pctx.url} canonicalizes to first page "
                               f"({pctx.canonical_url}) — devalues deeper paginated content",
                        severity=Severity.WARNING,
                    ))
                else:
                    # Non-self canonical for some other reason
                    findings.append(_mk(
                        rule, url=pctx.url,
                        detected=f"Non-self canonical: {pctx.canonical_url}",
                        expected="Self-referencing canonical",
                        evidence=f"canonical_url={pctx.canonical_url}",
                        detail=f"Pagination page {pctx.url} has non-self canonical: "
                               f"{pctx.canonical_url}",
                        severity=Severity.WARNING,
                    ))

    # ---- Faceted navigation checks ----
    # Group faceted URLs by base path
    faceted_by_base: dict[str, list[PageContext]] = defaultdict(list)
    for fctx in faceted_pages:
        bp = _base_path(fctx.url)
        faceted_by_base[bp].append(fctx)

    for base, fcontexts in faceted_by_base.items():
        # Parameter explosion: >20 faceted variants of same base path
        if len(fcontexts) > 20:
            findings.append(_mk(
                rule, url=base,
                detected=f"{len(fcontexts)} faceted URL variants of {base}",
                expected="<=20 faceted variants per base path, or proper canonicalization",
                evidence=f"faceted_variants={len(fcontexts)}",
                detail=f"Parameter explosion risk: {len(fcontexts)} faceted URL variants "
                       f"detected for {base}. Use canonical tags or URL parameter "
                       f"handling to consolidate.",
                severity=Severity.WARNING,
            ))

        # Check each faceted page
        for fctx in fcontexts:
            robots = (fctx.robots or "").lower()

            if fctx.canonical_url:
                canon_norm = fctx.canonical_url.rstrip("/")
                url_norm = fctx.url.rstrip("/")

                if canon_norm != url_norm:
                    # Faceted URL canonicalizes to base — expected, skip
                    pass
                else:
                    # Self-canonical AND indexable = duplicate content risk
                    if "noindex" not in robots:
                        findings.append(_mk(
                            rule, url=fctx.url,
                            detected="Self-canonical faceted URL, indexable",
                            expected="Faceted URLs should canonicalize to base or use noindex",
                            evidence=f"canonical_url={fctx.canonical_url}, robots={fctx.robots}",
                            detail=f"Faceted URL {fctx.url} is self-canonical and indexable "
                                   f"— may create duplicate content",
                            severity=Severity.OPPORTUNITY,
                        ))

    # ---- Summary INFO finding with evidence ----
    if pagination_pages or faceted_pages:
        evidence_parts = []
        if pagination_pages:
            evidence_parts.append(
                f"pagination_pages_detected={len(pagination_pages)}"
            )
        if faceted_pages:
            evidence_parts.append(
                f"faceted_urls_detected={len(faceted_pages)}"
            )
        findings.append(_mk(
            rule, url=site_ctx.base_url,
            detected=f"pagination_pages_detected={len(pagination_pages)}, "
                     f"faceted_urls_detected={len(faceted_pages)}",
            expected="Pagination and faceted URLs properly managed",
            evidence="; ".join(evidence_parts),
            detail=f"Found {len(pagination_pages)} pagination pages and "
                   f"{len(faceted_pages)} faceted/filter URLs. "
                   f"Review for proper canonicalization and indexability.",
            severity=Severity.INFO,
        ))

    return findings


# ============================================================
# Rule 38 — Permalink Structure
# ============================================================

# Patterns for detecting permalink structure types
_WP_DEFAULT_RE = re.compile(r"[?&]p=\d+")           # ?p=123 or &p=123
_INDEX_PHP_RE = re.compile(r"/index\.php[/?]|/index\.php$", re.IGNORECASE)
_CLEAN_SLUG_RE = re.compile(r"^/[a-z0-9\-_]+(?:/[a-z0-9\-_]+)*/?$")


def _permalink_structure_type(url: str) -> str:
    """Classify a URL's permalink structure type.

    Returns one of:
      "wp_default"  — ?p=123 WordPress default
      "index_php"   — contains /index.php
      "date"        — /YYYY/MM/... pattern
      "numeric"     — /123/ numeric slug
      "slug"        — /%postname%/ clean slug
      "html_ext"    — .html / .htm extension
      "other"       — unclassified
    """
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"

    if _WP_DEFAULT_RE.search(url):
        return "wp_default"
    if _INDEX_PHP_RE.search(path):
        return "index_php"
    if re.search(r"/\d{4}/\d{2}/", path):
        return "date"
    if re.search(r"/\d+/$", path) or re.search(r"/\d+$", path):
        return "numeric"
    if re.search(r"\.html?$", path, re.IGNORECASE):
        return "html_ext"
    if _CLEAN_SLUG_RE.search(path if path != "/" else "/clean-default"):
        return "slug"

    return "other"


def check_permalink(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Detect permalink structure issues across the site.

    Checks (grouped findings: one per issue type, affected URLs in evidence):
    1. ?p=123 WordPress default → WARNING
    2. index.php in public-facing URL → WARNING
    3. Mixed permalink structures across site → WARNING
    4. Trailing slash inconsistency (same content at /path and /path/) → ERROR
    5. Case variants (/Page and /page both 200) → ERROR
    6. .html / .htm extensions → NOT flagged (legitimate choice)
    7. Long URLs → NOT auto-flagged
    """
    findings: list[Finding] = []

    ok200 = [ctx for ctx in page_contexts if ctx.status_code == 200]
    if not ok200:
        return findings

    # Classify each URL
    wp_default_urls: list[str] = []
    index_php_urls: list[str] = []
    structure_counts: dict[str, list[str]] = defaultdict(list)

    for ctx in ok200:
        stype = _permalink_structure_type(ctx.url)
        structure_counts[stype].append(ctx.url)
        if stype == "wp_default":
            wp_default_urls.append(ctx.url)
        elif stype == "index_php":
            index_php_urls.append(ctx.url)

    # 1. WordPress default ?p=123
    if wp_default_urls:
        findings.append(_mk(
            rule, url=site_ctx.base_url,
            detected=f"WordPress default permalinks in {len(wp_default_urls)} URLs",
            expected="Clean, descriptive permalinks (e.g., /%postname%/)",
            evidence=f"wp_default_urls={wp_default_urls[:10]}",
            detail=f"Found {len(wp_default_urls)} URLs using default WordPress ?p=NNN "
                   f"format. Switch to 'Post name' permalink structure in "
                   f"Settings > Permalinks. Affected: {', '.join(wp_default_urls[:10])}"
                   f"{'...' if len(wp_default_urls) > 10 else ''}",
            severity=Severity.WARNING,
        ))

    # 2. index.php in public-facing URL
    if index_php_urls:
        findings.append(_mk(
            rule, url=site_ctx.base_url,
            detected=f"index.php in {len(index_php_urls)} public URLs",
            expected="Clean URLs without index.php",
            evidence=f"index_php_urls={index_php_urls[:10]}",
            detail=f"Found {len(index_php_urls)} URLs containing 'index.php' in the path. "
                   f"Remove index.php via permalink settings or URL rewrite rules. "
                   f"Affected: {', '.join(index_php_urls[:10])}"
                   f"{'...' if len(index_php_urls) > 10 else ''}",
            severity=Severity.WARNING,
        ))

    # 3. Mixed permalink structures
    non_other_types = {k: v for k, v in structure_counts.items() if k != "other"}
    if len(non_other_types) > 1:
        type_summary = "; ".join(
            f"{k}={len(v)}" for k, v in sorted(non_other_types.items())
        )
        findings.append(_mk(
            rule, url=site_ctx.base_url,
            detected=f"Mixed permalink structures: {type_summary}",
            expected="Consistent permalink structure across the site",
            evidence=f"structure_counts={dict(non_other_types)}",
            detail=f"Inconsistent permalink structures detected: {type_summary}. "
                   f"Standardize on one clean permalink format site-wide.",
            severity=Severity.WARNING,
        ))

    # 4. Trailing slash inconsistency
    norm_to_urls: dict[str, list[str]] = defaultdict(list)
    for ctx in ok200:
        parsed = urlparse(ctx.url)
        path = parsed.path
        norm_path = path.rstrip("/") if path != "/" else "/"
        norm_key = f"{parsed.scheme}://{parsed.netloc}{norm_path}"
        if parsed.query:
            norm_key += f"?{parsed.query}"
        norm_to_urls[norm_key].append(ctx.url)

    trailing_slash_conflicts: list[tuple[str, str]] = []
    for norm_key, urls in norm_to_urls.items():
        slashed = {u for u in urls if urlparse(u).path.endswith("/") and urlparse(u).path != "/"}
        unslashed = {u for u in urls if not urlparse(u).path.endswith("/") or urlparse(u).path == "/"}
        if slashed and unslashed:
            for sv in sorted(slashed)[:3]:
                for nv in sorted(unslashed)[:3]:
                    trailing_slash_conflicts.append((sv, nv))

    if trailing_slash_conflicts:
        examples = trailing_slash_conflicts[:10]
        findings.append(_mk(
            rule, url=site_ctx.base_url,
            detected=f"{len(trailing_slash_conflicts)} trailing-slash variant pairs",
            expected="Consistent trailing slash policy (pick one and redirect the other)",
            evidence=f"trailing_slash_conflicts={examples}",
            detail=f"Found {len(trailing_slash_conflicts)} URL pairs where the same content "
                   f"is accessible with and without a trailing slash. Implement 301 "
                   f"redirects to enforce one canonical form. Examples: {examples}",
            severity=Severity.ERROR,
        ))

    # 5. Case variants: /Page and /page both exist and return 200
    case_norm_to_urls: dict[str, list[str]] = defaultdict(list)
    for ctx in ok200:
        parsed = urlparse(ctx.url)
        lower_path = parsed.path.lower()
        lower_key = f"{parsed.scheme}://{parsed.netloc}{lower_path}"
        if parsed.query:
            lower_key += f"?{parsed.query.lower()}"
        case_norm_to_urls[lower_key].append(ctx.url)

    case_conflicts: list[tuple[str, str]] = []
    for lower_key, urls in case_norm_to_urls.items():
        if len(urls) <= 1:
            continue
        unique_paths = set(urlparse(u).path for u in urls)
        if len(unique_paths) <= 1:
            continue
        for u1 in sorted(urls):
            for u2 in sorted(urls):
                if u1 >= u2:
                    continue
                p1 = urlparse(u1).path
                p2 = urlparse(u2).path
                if p1.lower() == p2.lower() and p1 != p2:
                    case_conflicts.append((u1, u2))
                    if len(case_conflicts) >= 10:
                        break
            if len(case_conflicts) >= 10:
                break

    if case_conflicts:
        findings.append(_mk(
            rule, url=site_ctx.base_url,
            detected=f"{sum(1 for urls in case_norm_to_urls.values() if len(urls) > 1 and len(set(urlparse(u).path for u in urls)) > 1)} case-variant path groups",
            expected="Single canonical case for all URL paths (lowercase recommended)",
            evidence=f"case_conflicts={case_conflicts[:10]}",
            detail=f"Found case-variant URLs serving the same content. "
                   f"Use lowercase URLs and 301 redirect uppercase variants. "
                   f"Examples: {case_conflicts[:10]}",
            severity=Severity.ERROR,
        ))

    return findings


# ============================================================
# Rule 49 — URL Normalization
# ============================================================

def check_url_normalization(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Detect URL normalization issues across all crawled URLs.

    Checks (grouped findings by issue type with affected URL lists):
    1. Uppercase characters in path → OPPORTUNITY
    2. Double slash // in path → WARNING
    3. Spaces or %20 in URL → WARNING
    4. Non-ASCII characters in URL → INFO
    5. Underscores _ in path segments → OPPORTUNITY
    6. index.html / index.php at end of path → WARNING
    7. Trailing slash inconsistency across site → grouped finding with count
    8. Case-equivalent duplicate URLs (same path, different case) → ERROR
    """
    findings: list[Finding] = []

    # Issue collectors
    uppercase_paths: list[str] = []
    double_slash_urls: list[str] = []
    space_urls: list[str] = []
    non_ascii_urls: list[str] = []
    underscore_paths: list[str] = []
    index_file_urls: list[str] = []

    # For cross-URL analysis
    trailing_slash_variants: dict[str, list[str]] = defaultdict(list)
    case_norm_to_urls: dict[str, list[str]] = defaultdict(list)

    for ctx in page_contexts:
        url = ctx.url
        if not url:
            continue
        parsed = urlparse(url)
        path = parsed.path

        # 1. Uppercase characters in path
        if path != path.lower():
            uppercase_paths.append(url)

        # 2. Double slash in path (after scheme://)
        path_part = url.split("://", 1)[-1] if "://" in url else url
        if "//" in path_part:
            double_slash_urls.append(url)

        # 3. Spaces or %20
        if " " in url or "%20" in url.lower():
            space_urls.append(url)

        # 4. Non-ASCII characters
        if any(ord(c) > 127 for c in url):
            non_ascii_urls.append(url)

        # 5. Underscores in path segments
        path_no_slash = path.strip("/")
        segments = [s for s in path_no_slash.split("/") if s]
        for seg in segments:
            base_seg = seg.rsplit(".", 1)[0] if "." in seg else seg
            if "_" in base_seg:
                underscore_paths.append(url)
                break

        # 6. index.html or index.php at end of path
        if re.search(r"/index\.(html?|php)$", path, re.IGNORECASE):
            index_file_urls.append(url)

        # 7. Trailing slash variants (pre-collection)
        norm_path = path.rstrip("/") if path != "/" else "/"
        norm_key = f"{parsed.scheme}://{parsed.netloc}{norm_path}"
        if parsed.query:
            norm_key += f"?{parsed.query}"
        trailing_slash_variants[norm_key].append(url)

        # 8. Case-equivalent duplicates (pre-collection)
        lower_full = f"{parsed.scheme}://{parsed.netloc}{path.lower()}"
        if parsed.query:
            lower_full += f"?{parsed.query.lower()}"
        case_norm_to_urls[lower_full].append(url)

    # ---- Report grouped findings ----

    # 1. Uppercase in path
    if uppercase_paths:
        findings.append(_mk(
            rule, url=site_ctx.base_url,
            detected=f"Uppercase in {len(uppercase_paths)} URL paths",
            expected="All-lowercase URL paths (RFC 3986 paths are case-sensitive)",
            evidence=f"uppercase_url_count={len(uppercase_paths)}",
            detail=f"Found {len(uppercase_paths)} URLs with uppercase characters in path. "
                   f"Normalize to lowercase for consistency and duplicate-content "
                   f"prevention. Affected: {', '.join(uppercase_paths[:10])}"
                   f"{'...' if len(uppercase_paths) > 10 else ''}",
            severity=Severity.OPPORTUNITY,
        ))

    # 2. Double slash
    if double_slash_urls:
        findings.append(_mk(
            rule, url=site_ctx.base_url,
            detected=f"Double slash in {len(double_slash_urls)} URLs",
            expected="No double slashes in URL paths",
            evidence=f"double_slash_count={len(double_slash_urls)}",
            detail=f"Found {len(double_slash_urls)} URLs with '//' in the path. "
                   f"This may cause crawl inefficiency or broken relative links. "
                   f"Affected: {', '.join(double_slash_urls[:10])}"
                   f"{'...' if len(double_slash_urls) > 10 else ''}",
            severity=Severity.WARNING,
        ))

    # 3. Spaces or %20
    if space_urls:
        findings.append(_mk(
            rule, url=site_ctx.base_url,
            detected=f"Spaces or %20 in {len(space_urls)} URLs",
            expected="URLs with hyphens instead of spaces, no raw spaces",
            evidence=f"space_url_count={len(space_urls)}",
            detail=f"Found {len(space_urls)} URLs containing spaces or %20 encoding. "
                   f"Replace spaces with hyphens for cleaner, more readable URLs. "
                   f"Affected: {', '.join(space_urls[:10])}"
                   f"{'...' if len(space_urls) > 10 else ''}",
            severity=Severity.WARNING,
        ))

    # 4. Non-ASCII characters
    if non_ascii_urls:
        findings.append(_mk(
            rule, url=site_ctx.base_url,
            detected=f"Non-ASCII in {len(non_ascii_urls)} URLs",
            expected="ASCII-only URLs (or proper Punycode for IDNs)",
            evidence=f"non_ascii_count={len(non_ascii_urls)}",
            detail=f"Found {len(non_ascii_urls)} URLs with non-ASCII characters. "
                   f"IRIs are valid but may cause issues with older tools or link "
                   f"sharing. Affected: {', '.join(non_ascii_urls[:10])}"
                   f"{'...' if len(non_ascii_urls) > 10 else ''}",
            severity=Severity.INFO,
        ))

    # 5. Underscores in path segments
    if underscore_paths:
        findings.append(_mk(
            rule, url=site_ctx.base_url,
            detected=f"Underscores in {len(underscore_paths)} URL paths",
            expected="Hyphens as word separators in URLs (SEO best practice)",
            evidence=f"underscore_url_count={len(underscore_paths)}",
            detail=f"Found {len(underscore_paths)} URLs using underscores in path "
                   f"segments. Google treats hyphens as word separators but "
                   f"underscores as joiners. Prefer hyphens for SEO. "
                   f"Affected: {', '.join(underscore_paths[:10])}"
                   f"{'...' if len(underscore_paths) > 10 else ''}",
            severity=Severity.OPPORTUNITY,
        ))

    # 6. index.html / index.php at end of path
    if index_file_urls:
        findings.append(_mk(
            rule, url=site_ctx.base_url,
            detected=f"index.html/php suffix in {len(index_file_urls)} URLs",
            expected="Clean URLs without index.html or index.php suffix",
            evidence=f"index_file_count={len(index_file_urls)}",
            detail=f"Found {len(index_file_urls)} URLs ending with index.html or "
                   f"index.php. This creates duplicate content with the directory "
                   f"URL. Use 301 redirects or rewrite rules. "
                   f"Affected: {', '.join(index_file_urls[:10])}"
                   f"{'...' if len(index_file_urls) > 10 else ''}",
            severity=Severity.WARNING,
        ))

    # 7. Trailing slash inconsistency
    trailing_slash_conflicts: list[tuple[str, str]] = []
    for norm_key, urls in trailing_slash_variants.items():
        slashed = {u for u in urls if urlparse(u).path.endswith("/") and urlparse(u).path != "/"}
        unslashed = {u for u in urls if not urlparse(u).path.endswith("/") or urlparse(u).path == "/"}
        if slashed and unslashed:
            for sv in sorted(slashed)[:2]:
                for nv in sorted(unslashed)[:2]:
                    trailing_slash_conflicts.append((sv, nv))

    if trailing_slash_conflicts:
        examples = trailing_slash_conflicts[:10]
        findings.append(_mk(
            rule, url=site_ctx.base_url,
            detected=f"{len(trailing_slash_conflicts)} trailing-slash variant pairs",
            expected="Consistent trailing slash policy across site",
            evidence=f"trailing_slash_count={len(trailing_slash_conflicts)}",
            detail=f"Found {len(trailing_slash_conflicts)} URL pairs with inconsistent "
                   f"trailing slashes. Choose a canonical form (with or without "
                   f"trailing slash) and enforce via 301 redirects. "
                   f"Examples: {examples}",
            severity=Severity.OPPORTUNITY,
        ))

    # 8. Case-equivalent duplicate URLs (same path, different case) → ERROR
    case_duplicate_groups: list[list[str]] = []
    for lower_key, urls in case_norm_to_urls.items():
        if len(urls) > 1:
            unique_paths = set(urlparse(u).path for u in urls)
            if len(unique_paths) > 1:
                case_duplicate_groups.append(sorted(urls))

    if case_duplicate_groups:
        findings.append(_mk(
            rule, url=site_ctx.base_url,
            detected=f"{len(case_duplicate_groups)} case-duplicate URL groups",
            expected="Single canonical case for each URL path",
            evidence=f"case_duplicate_count={len(case_duplicate_groups)}",
            detail=f"Found {len(case_duplicate_groups)} groups of URLs differing only "
                   f"in letter case — this creates severe duplicate content. "
                   f"Canonicalize to lowercase and 301 redirect. "
                   f"Examples: {case_duplicate_groups[:10]}",
            severity=Severity.ERROR,
        ))

    return findings


# ============================================================
# Rule 50 — Redirect Relevance (heuristic)
# ============================================================

def _jaccard_path_similarity(url1: str, url2: str) -> float:
    """Compute Jaccard similarity of path tokens between two URLs.

    Tokenizes each URL path by '/', lowercasing segments, then computes
    intersection / union of the token sets. Returns 0.0–1.0.
    """
    def _tokens(u: str) -> set[str]:
        p = urlparse(u).path.strip("/")
        return set(seg.lower() for seg in p.split("/") if seg)

    t1 = _tokens(url1)
    t2 = _tokens(url2)

    if not t1 and not t2:
        return 1.0
    if not t1 or not t2:
        return 0.0

    return len(t1 & t2) / len(t1 | t2)


def _is_homepage(url: str, base_url: str = "") -> bool:
    """Check if a URL is likely the homepage."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    if path in ("", "/"):
        return True
    if base_url and url.rstrip("/") == base_url.rstrip("/"):
        return True
    return False


def _extract_redirect_info(
    page_contexts: list[PageContext],
    data: dict,
) -> list[dict]:
    """Extract redirect (source -> target) pairs from available data.

    Checks multiple sources in priority order:
    1. data["crawl"]["redirects"] — crawl-level redirect chain data
    2. PageContext response_headers["Location"] — per-page redirect target

    Returns list of dicts: {source_url, target_url, status_code}
    """
    redirect_map: dict[str, dict] = {}  # source_url -> redirect info (dedup)

    # Source 1: Crawl-level redirect data
    crawl = (data or {}).get("crawl", {}) or {}
    crawl_redirects = crawl.get("redirects", []) or []
    for redir in crawl_redirects:
        source = redir.get("source") or redir.get("url") or ""
        chain = redir.get("chain", [])
        target = redir.get("target") or redir.get("destination") or ""
        status = redir.get("status") or redir.get("status_code") or 301

        if chain and not target:
            target = chain[0]
        if source and target and source not in redirect_map:
            redirect_map[source] = {
                "source_url": source,
                "target_url": target,
                "status_code": int(status) if status else 301,
            }

    # Source 2: PageContext response headers
    for ctx in page_contexts:
        if ctx.status_code not in (301, 302, 307, 308):
            continue
        if ctx.url in redirect_map:
            continue

        target = None
        try:
            headers = ctx.response_headers
            if headers and isinstance(headers, dict):
                for key, value in headers.items():
                    if key.lower() == "location":
                        target = value
                        break
        except Exception:
            pass

        if target and ctx.url not in redirect_map:
            redirect_map[ctx.url] = {
                "source_url": ctx.url,
                "target_url": target,
                "status_code": ctx.status_code,
            }

    return list(redirect_map.values())


def check_redirect_relevance(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Heuristic check for redirect relevance.

    Uses path-token Jaccard similarity to detect potentially unrelated
    redirects. All findings include confidence level (HIGH/MEDIUM/LOW).

    Confidence rules:
      - LOW  -> Severity.OPPORTUNITY with "Manual Review Recommended"
      - MEDIUM -> Severity.OPPORTUNITY
      - HIGH -> Severity.WARNING

    Does NOT flag: highly similar paths (>=0.7), source=homepage.
    """
    findings: list[Finding] = []

    redirects = _extract_redirect_info(page_contexts, data)
    if not redirects:
        return findings

    base_url = site_ctx.base_url

    # Build url -> PageContext lookup for lang data
    url_to_ctx: dict[str, PageContext] = {}
    for ctx in page_contexts:
        if ctx.url:
            url_to_ctx[ctx.url] = ctx

    # Group redirects by target
    target_to_sources: dict[str, list[dict]] = defaultdict(list)
    for r in redirects:
        target_to_sources[r["target_url"]].append(r)

    checked_sources: set[str] = set()

    for target_url, sources in target_to_sources.items():
        for r in sources:
            source_url = r["source_url"]
            status_code = r["status_code"]

            if source_url in checked_sources:
                continue

            similarity = _jaccard_path_similarity(source_url, target_url)

            # Skip highly similar redirects — expected behavior
            if similarity >= 0.7:
                continue

            # Skip source = homepage (normal/expected)
            if _is_homepage(source_url, base_url):
                continue

            target_is_home = _is_homepage(target_url, base_url)

            # Cross-language detection
            source_lang = None
            target_lang = None
            src_ctx = url_to_ctx.get(source_url)
            tgt_ctx = url_to_ctx.get(target_url)
            if src_ctx:
                source_lang = src_ctx.lang
            if tgt_ctx:
                target_lang = tgt_ctx.lang

            cross_lang = bool(
                source_lang and target_lang and source_lang != target_lang
            )

            # ---- Confidence assignment ----
            confidence: str
            severity: Severity

            if similarity < 0.3:
                if target_is_home:
                    # Unrelated URL -> homepage
                    confidence = "LOW"
                    severity = Severity.OPPORTUNITY
                else:
                    # Check if many low-similarity sources redirect here
                    low_sim_count = sum(
                        1 for s in sources
                        if _jaccard_path_similarity(s["source_url"], target_url) < 0.3
                        and not _is_homepage(s["source_url"], base_url)
                    )
                    if low_sim_count >= 3:
                        confidence = "MEDIUM"
                        severity = Severity.OPPORTUNITY
                    else:
                        confidence = "LOW"
                        severity = Severity.OPPORTUNITY
            elif similarity < 0.5:
                confidence = "MEDIUM"
                severity = Severity.OPPORTUNITY
            else:
                # 0.5 <= similarity < 0.7
                confidence = "MEDIUM"
                severity = Severity.OPPORTUNITY

            # Cross-language overrides to LOW
            if cross_lang and confidence != "HIGH":
                confidence = "LOW"
                severity = Severity.OPPORTUNITY

            # ---- Build finding ----
            detail_parts = [
                f"Redirect {status_code}: {source_url} -> {target_url}",
                f"Path-token Jaccard similarity: {similarity:.2f}",
                f"Confidence: {confidence}",
            ]
            if target_is_home:
                detail_parts.append(
                    "Target is homepage — may indicate overly broad redirect "
                    "catch-all rule"
                )
            if cross_lang:
                detail_parts.append(
                    f"Cross-language redirect: source lang={source_lang}, "
                    f"target lang={target_lang}"
                )
            if confidence == "LOW":
                detail_parts.append("Manual Review Recommended")

            # Map confidence string to float
            confidence_map = {"HIGH": 0.9, "MEDIUM": 0.6, "LOW": 0.3}

            findings.append(_mk(
                rule,
                url=source_url,
                detected=f"Redirect to {target_url} (similarity={similarity:.2f})",
                expected="Redirect to contextually relevant URL, or remove unnecessary redirect",
                evidence=(
                    f"source={source_url}, target={target_url}, "
                    f"similarity={similarity:.2f}, "
                    f"status={status_code}, "
                    f"conf={confidence}, "
                    f"cross_lang={cross_lang}"
                ),
                detail=" | ".join(detail_parts),
                severity=severity,
                confidence=confidence_map.get(confidence, 0.5),
            ))

            checked_sources.add(source_url)

    # ---- Aggregate: multiple low-similarity sources -> same target ----
    for target_url, sources in target_to_sources.items():
        target_is_home = _is_homepage(target_url, base_url)
        low_sim_sources = [
            s for s in sources
            if not _is_homepage(s["source_url"], base_url)
            and _jaccard_path_similarity(s["source_url"], target_url) < 0.3
        ]

        if len(low_sim_sources) > 3 and not target_is_home:
            source_list = [s["source_url"] for s in low_sim_sources[:10]]
            findings.append(_mk(
                rule,
                url=target_url,
                detected=(
                    f"{len(low_sim_sources)} low-similarity sources "
                    f"redirect to {target_url}"
                ),
                expected="Each redirect should point to contextually relevant target",
                evidence=f"low_sim_sources={source_list}, target={target_url}",
                detail=(
                    f"Aggregated finding: {len(low_sim_sources)} URLs with low path "
                    f"similarity all redirect to {target_url}. Review whether these "
                    f"redirects are intentional or should point to more specific "
                    f"destinations. Manual Review Recommended."
                ),
                severity=Severity.OPPORTUNITY,
                confidence=0.3,
            ))

    return findings
