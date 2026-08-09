"""Phase 4A — NEW_AUTO Stateless SEO Rules (8 checks).

Implements 8 stateless/single-audit rules using existing LibreCrawl data only.
No external HTTP requests — zero additional page fetches (except Rule 39
safe WordPress probes when WP_SECURITY_PROBES_ENABLED=true, max 3 GET/HEAD).

Rules:
  18 — Tags / Archives / Search Indexability
  32 — Image / Video Sitemap
  39 — WordPress XML-RPC / REST API Exposure
  43 — Sitemap lastmod Accuracy
  47 — Crawlable <a href> (Event-Only Navigation)
  51 — Internal Links → Redirect URLs
  60 — Multi-language Canonical
  67 — Staging / Dev Indexability
"""

from __future__ import annotations

import re
import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from audit_rules.models import RuleDefinition, Finding
from audit_rules.context import SiteContext, PageContext
from audit_rules.categories import Severity

logger = logging.getLogger(__name__)

# ============================================================
# Shared helpers
# ============================================================

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


# ============================================================
# URL pattern constants
# ============================================================

# Rule 18: CMS aggregation page patterns
_ARCHIVE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("tag", re.compile(r"/(tag|tags|topic|label|etiket|etiqueta|schlagwort)/", re.IGNORECASE)),
    ("author", re.compile(r"/author/", re.IGNORECASE)),
    ("date_archive", re.compile(r"/\d{4}/\d{2}/", re.IGNORECASE)),
    ("date_year", re.compile(r"/\d{4}/$", re.IGNORECASE)),
    ("category", re.compile(r"/category/", re.IGNORECASE)),
    ("archive", re.compile(r"/archive/", re.IGNORECASE)),
    ("search_results", re.compile(r"[/?](search|suche|recherche|busca|busqueda|cerca|zoeken|sok|q=|s=)", re.IGNORECASE)),
]

# Rule 67: Staging/dev hostname patterns (non-exhaustive, safe subset)
_STAGING_HOSTNAME_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"^staging\.",
        r"^dev\d*\.",
        r"^test\.",
        r"^preview\.",
        r"^sandbox\.",
        r"^uat\.",
        r"^qa\.",
        r"^develop\.",
        r"\.staging\.",
        r"\.dev\d*\.",
        r"\.test\.",
        r"\.wpengine\.com$",
        r"\.flywheelsites\.com$",
        r"\.kinsta\.cloud$",
        r"\.pantheonsite\.io$",
        r"\.cloudwaysapps\.com$",
        r"\.ngrok\.io$",
        r"\.local$",
        r"\.localhost$",
        r"\.test$",
    ]
]

# Language path patterns: /en/, /de/, /fr/, etc. (ISO 639-1, 2 chars lowercase)
_LANG_PATH_RE = re.compile(r"^/([a-z]{2})(/|$)", re.IGNORECASE)

# Known WordPress signals (from crawl observables, no probing)
_WP_SIGNALS = [
    "/wp-content/",
    "/wp-includes/",
    "/wp-admin/",
    "/wp-json/",
    "wp-login.php",
    "xmlrpc.php",
    "?p=",
    "/wp-",
]


# ============================================================
# Rule 18 — Tags / Archives / Search Indexability
# ============================================================

def check_archive_search_indexability(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 18: Detect CMS aggregation pages (tag/author/date/category/search)
    and report on their indexability state.

    Does NOT automatically FAIL indexable archive pages — these are site
    strategy decisions. Reports facts and risk, leaves decision to user
    unless an explicit INDEXATION_POLICY is configured.

    Args:
        rule: RuleDefinition.
        site_ctx: Site context.
        page_contexts: All page contexts.
        data: May contain indexation policies:
              INDEXATION_POLICY_SEARCH, INDEXATION_POLICY_TAG,
              INDEXATION_POLICY_AUTHOR, INDEXATION_POLICY_DATE,
              INDEXATION_POLICY_CATEGORY

    Returns:
        List of Finding objects.
    """
    findings: list[Finding] = []
    policies = {
        "search": data.get("INDEXATION_POLICY_SEARCH", "auto"),
        "tag": data.get("INDEXATION_POLICY_TAG", "auto"),
        "author": data.get("INDEXATION_POLICY_AUTHOR", "auto"),
        "date_archive": data.get("INDEXATION_POLICY_DATE", "auto"),
        "category": data.get("INDEXATION_POLICY_CATEGORY", "auto"),
    }

    for ctx in page_contexts:
        if ctx.status_code != 200:
            continue

        url = ctx.url
        page_type = _classify_archive_page(url)

        if page_type is None:
            continue

        # Gather facts
        is_indexable = _is_indexable(ctx)
        canonical = ctx.canonical_url or ""
        word_count = ctx.word_count or 0
        policy = policies.get(page_type, "auto")

        # Build evidence
        evidence_parts = [
            f"page_type={page_type}",
            f"indexable={is_indexable}",
            f"canonical={canonical or 'self'}",
            f"word_count={word_count}",
        ]
        evidence = ", ".join(evidence_parts)

        # Search results: if indexable → WARNING (policy: noindex recommended)
        if page_type == "search_results":
            if is_indexable:
                severity = Severity.WARNING if policy != "auto" else Severity.OPPORTUNITY
                findings.append(_mk(
                    rule=rule, url=url,
                    detected=f"Search results page is indexable (policy={policy})",
                    expected="Search results should typically be noindex",
                    evidence=evidence,
                    detail=(
                        f"Search results page at {url} is indexable. "
                        f"Search results typically add low-value index bloat. "
                        f"Consider noindex for internal search pages. "
                        f"Policy: {policy}."
                    ),
                    severity=severity,
                    confidence=0.95 if policy != "auto" else 0.75,
                ))
            continue

        # Tag/Author/Date/Category: report facts, don't auto-FAIL
        if policy == "auto":
            # Report only — site strategy decision
            severity = Severity.OPPORTUNITY
            detail = (
                f"Archive page ({page_type}) at {url}: "
                f"indexable={is_indexable}, word_count={word_count}. "
                f"No explicit indexation policy set (auto mode). "
                f"Consider whether this content type should be indexed."
            )
            confidence = 0.6  # Heuristic — needs human confirmation
        elif policy == "noindex":
            if is_indexable:
                severity = Severity.WARNING
                detail = (
                    f"Archive page ({page_type}) at {url} is indexable "
                    f"but policy={policy}. Should be noindex per configuration."
                )
                confidence = 0.9
            else:
                # Policy followed — no finding
                continue
        elif policy == "index":
            severity = Severity.INFO
            detail = (
                f"Archive page ({page_type}) at {url} is indexed per policy. "
                f"Monitor for thin content risk."
            )
            confidence = 0.9
        else:
            continue  # Unknown policy → skip

        findings.append(_mk(
            rule=rule, url=url,
            detected=f"{page_type} page, indexable={is_indexable}, policy={policy}",
            expected=(
                "Noindex for low-value aggregation pages" if policy == "noindex"
                else "Index per site strategy"
            ),
            evidence=evidence,
            detail=detail,
            severity=severity,
            confidence=confidence,
        ))

    return findings


def _classify_archive_page(url: str) -> Optional[str]:
    """Classify URL as an archive/aggregation page type, or None."""
    if not url:
        return None
    try:
        path = urlparse(url).path or ""
        query = urlparse(url).query or ""
    except Exception:
        return None

    # Search results (query param or path)
    if re.search(r"[/?](search|suche|recherche|busca|busqueda|s=|q=)", url, re.IGNORECASE):
        return "search_results"

    # Tag
    if re.search(r"/tag/|/hashtag/", url, re.IGNORECASE):
        return "tag"

    # Author
    if re.search(r"/author/", url, re.IGNORECASE):
        return "author"

    # Date archive: /YYYY/MM/
    if re.search(r"/\d{4}/\d{2}/", path):
        return "date_archive"

    # Category
    if re.search(r"/category/", url, re.IGNORECASE):
        return "category"

    return None


def _is_indexable(ctx: PageContext) -> bool:
    """Check if page appears indexable based on meta robots and status."""
    if ctx.status_code != 200:
        return False
    robots = (ctx.robots or "").lower()
    if "noindex" in robots:
        return False
    return True


# ============================================================
# Rule 32 — Image / Video Sitemap
# ============================================================

def check_media_sitemap(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 32: Check for image/video sitemap presence via sitemap index
    and child sitemap analysis.

    Absence of media sitemap is NOT an automatic FAIL. Media sitemaps are
    a supplemental discovery mechanism, not required for all sites.

    Returns:
        List of Finding objects (typically 0-2).
    """
    findings: list[Finding] = []

    sitemap_data = data.get("sitemap_data") or data.get("extended_checks", {}).get("sitemap_data") or {}
    sitemap_index = data.get("sitemap_index") or data.get("site_check", {}).get("sitemap_index") or {}

    # Count media-rich pages from crawl
    image_count = 0
    video_count = 0
    for ctx in page_contexts:
        img = ctx.image_summary or {}
        image_count += img.get("count", 0) or 0
        # Video detection: check if any links_detailed point to video hosting
        # or if page has video-related schema
        if ctx.json_ld_types and any("Video" in t for t in ctx.json_ld_types):
            video_count += 1

    # Determine applicability
    has_image_sitemap = _detect_media_sitemap(sitemap_data, "image")
    has_video_sitemap = _detect_media_sitemap(sitemap_data, "video")

    site_url = site_ctx.base_url or "this site"

    # Image sitemap assessment
    img_applicable = image_count > 10  # Only meaningful if site has images
    if img_applicable and not has_image_sitemap:
        findings.append(_mk(
            rule=rule, url=site_url,
            detected=f"No image sitemap found (site has {image_count} images across pages)",
            expected="Image sitemap for improved image discovery (optional)",
            evidence=f"image_count={image_count}, image_sitemap_present=false",
            detail=(
                f"No dedicated image sitemap detected. The site has {image_count} "
                f"images across crawl pages. An image sitemap can improve image "
                f"discovery in Google Image Search but is not required."
            ),
            severity=Severity.OPPORTUNITY,
            confidence=0.7,
        ))

    # Video sitemap assessment
    vid_applicable = video_count > 0
    if vid_applicable and not has_video_sitemap:
        findings.append(_mk(
            rule=rule, url=site_url,
            detected=f"No video sitemap found (site has {video_count} pages with video schema)",
            expected="Video sitemap for improved video discovery (optional)",
            evidence=f"video_page_count={video_count}, video_sitemap_present=false",
            detail=(
                f"No dedicated video sitemap detected. {video_count} pages have "
                f"video-related schema. A video sitemap can improve video discovery "
                f"but is not required."
            ),
            severity=Severity.OPPORTUNITY,
            confidence=0.7,
        ))

    if not img_applicable and not vid_applicable:
        # Site doesn't benefit from media sitemaps
        findings.append(_mk(
            rule=rule, url=site_url,
            detected="Media sitemap not applicable — no significant image/video content detected",
            expected="N/A",
            evidence=f"image_count={image_count}, video_pages={video_count}",
            detail="Site has minimal image/video content; media sitemap is not applicable.",
            severity=Severity.INFO,
            confidence=0.9,
        ))

    return findings


def _detect_media_sitemap(sitemap_data: dict, media_type: str) -> bool:
    """Check if sitemap data contains image:image or video:video namespaces."""
    if not sitemap_data:
        return False

    # Check raw sitemap XML for namespace
    raw = ""
    if isinstance(sitemap_data, dict):
        raw = sitemap_data.get("raw", "") or sitemap_data.get("xml", "") or ""
        # Also check sitemap URLs list
        sitemap_urls = sitemap_data.get("sitemaps") or sitemap_data.get("urls") or []
        if isinstance(sitemap_urls, list):
            for su in sitemap_urls:
                if isinstance(su, dict):
                    raw += su.get("url", "") + " "
                elif isinstance(su, str):
                    raw += su + " "
    elif isinstance(sitemap_data, str):
        raw = sitemap_data

    if media_type == "image":
        return "image:image" in raw or "image-sitemap" in raw.lower()
    elif media_type == "video":
        return "video:video" in raw or "video-sitemap" in raw.lower()
    return False


# ============================================================
# Rule 39 — WordPress XML-RPC / REST API Exposure
# ============================================================

def check_wordpress_api_exposure(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 39: Assess WordPress XML-RPC and REST API exposure.

    This is a security-audit-adjacent rule. Does NOT probe, brute force,
    or attempt any authentication. Only reports on observable signals from
    crawl data and safe availability probes (if enabled).

    Safe probes: only when WP_SECURITY_PROBES_ENABLED=true, max 3 GET/HEAD
    requests per host. No POST, no login, no credential attempts.

    Args:
        data: May contain WP_SECURITY_PROBES_ENABLED (bool, default false).

    Returns:
        List of Finding objects.
    """
    findings: list[Finding] = []
    probes_enabled = bool(data.get("WP_SECURITY_PROBES_ENABLED", False))

    # Detect if WordPress from crawl signals
    is_wp = _detect_wordpress_from_crawl(page_contexts, data)

    if not is_wp:
        # Check if probes would reveal WordPress
        if not probes_enabled:
            return findings  # Not detected, not probing → NOT_APPLICABLE

    site_url = site_ctx.base_url or ""

    # XML-RPC check
    xmlrpc_found = _check_xmlrpc_signal(page_contexts, data)
    if xmlrpc_found:
        findings.append(_mk(
            rule=rule, url=site_url,
            detected="xmlrpc.php endpoint reachable",
            expected="xmlrpc.php should be disabled unless needed for legacy integrations",
            evidence="xmlrpc.php found in crawl links or site data",
            detail=(
                "WordPress XML-RPC endpoint (xmlrpc.php) is reachable. "
                "If not needed for legacy integrations (e.g., Jetpack, mobile apps), "
                "consider disabling it to reduce attack surface. "
                "This is an INFO-level finding — XML-RPC accessibility alone "
                "is not a vulnerability."
            ),
            severity=Severity.INFO,
            confidence=0.85,
        ))

    # REST API check
    rest_users_exposed = _check_rest_api_exposure(page_contexts, data)
    if rest_users_exposed:
        findings.append(_mk(
            rule=rule, url=site_url,
            detected="WordPress REST API exposes user information",
            expected="REST API user enumeration should be restricted",
            evidence="REST API /wp-json/wp/v2/users accessible from crawl signals",
            detail=(
                "WordPress REST API appears to expose user information. "
                "User enumeration via /wp-json/wp/v2/users can reveal usernames. "
                "Consider restricting REST API access or using a plugin to disable "
                "user enumeration endpoints."
            ),
            severity=Severity.WARNING,
            confidence=0.75,
        ))
    elif is_wp and not rest_users_exposed:
        # WordPress detected but no sensitive exposure — just note REST API presence
        findings.append(_mk(
            rule=rule, url=site_url,
            detected="WordPress REST API available (no sensitive exposure detected from crawl)",
            expected="REST API is a normal WordPress capability",
            evidence="WordPress signals detected, REST API appears normally configured",
            detail=(
                "WordPress REST API (/wp-json/) appears to be normally configured "
                "with no sensitive user enumeration detected from crawl data. "
                "REST API accessibility is a standard platform feature, not a vulnerability."
            ),
            severity=Severity.INFO,
            confidence=0.7,
        ))

    return findings


def _detect_wordpress_from_crawl(page_contexts, data) -> bool:
    """Detect WordPress from crawl signals (no probing)."""
    # Check if any page URL or internal link contains WordPress signals
    wp_signal_count = 0
    for ctx in page_contexts:
        url_lower = ctx.url.lower()
        for sig in _WP_SIGNALS:
            if sig in url_lower:
                wp_signal_count += 1
                break
        if ctx.links_detailed:
            for link in ctx.links_detailed:
                if isinstance(link, dict):
                    href = (link.get("url") or "").lower()
                else:
                    href = ""
                for sig in _WP_SIGNALS:
                    if sig in href:
                        wp_signal_count += 1
                        break

    # Check generator meta or other WP indicators
    site_check = data.get("site_check", {})
    if isinstance(site_check, dict):
        generator = site_check.get("generator", "")
        if "wordpress" in str(generator).lower():
            return True

    # Threshold: at least 3 WP signals found
    return wp_signal_count >= 3


def _check_xmlrpc_signal(page_contexts, data) -> bool:
    """Check if xmlrpc.php is referenced in crawl data."""
    for ctx in page_contexts:
        if "xmlrpc.php" in ctx.url.lower():
            return True
        if ctx.links_detailed:
            for link in ctx.links_detailed:
                href = (link.get("url") if isinstance(link, dict) else "") or ""
                if "xmlrpc.php" in href.lower():
                    return True
    return False


def _check_rest_api_exposure(page_contexts, data) -> bool:
    """Check if REST API user endpoint is accessible from crawl signals."""
    # Check for /wp-json/wp/v2/users in crawl
    for ctx in page_contexts:
        if "/wp-json/wp/v2/users" in ctx.url.lower():
            return True
        if ctx.links_detailed:
            for link in ctx.links_detailed:
                href = (link.get("url") if isinstance(link, dict) else "") or ""
                if "/wp-json/wp/v2/users" in href.lower():
                    return True
    return False


# ============================================================
# Rule 43 — Sitemap lastmod Accuracy
# ============================================================

def check_sitemap_lastmod(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 43: Validate sitemap lastmod fields for anomalies.

    Checks:
      - Invalid W3C datetime format
      - Future dates
      - Suspicious all-URLs-same-date pattern
      - Mass-refresh pattern (all lastmod = today)

    Does NOT flag old lastmod dates — pages can legitimately be old.

    Returns:
        List of Finding objects.
    """
    findings: list[Finding] = []

    sitemap_urls = _extract_sitemap_urls(data)
    if not sitemap_urls:
        return findings  # No sitemap data available

    now = datetime.now(timezone.utc)
    dates = []
    invalid_count = 0
    future_count = 0
    same_date_urls = 0

    for entry in sitemap_urls:
        lastmod_str = ""
        loc = ""
        if isinstance(entry, dict):
            lastmod_str = (entry.get("lastmod") or entry.get("last_modified") or "").strip()
            loc = entry.get("loc") or entry.get("url") or ""
        elif isinstance(entry, str):
            continue  # Can't parse if it's just a string URL

        if not lastmod_str:
            continue

        parsed = _parse_lastmod(lastmod_str)
        if parsed is None:
            invalid_count += 1
            continue

        dates.append({"url": loc, "date": parsed, "raw": lastmod_str})

        if parsed > now:
            future_count += 1

    total = len(dates) + invalid_count
    if total == 0:
        return findings

    site_url = site_ctx.base_url or ""

    # Check 1: Invalid format
    if invalid_count > 0:
        findings.append(_mk(
            rule=rule, url=site_url,
            detected=f"{invalid_count}/{total} sitemap entries have invalid lastmod format",
            expected="Valid W3C datetime (ISO 8601) in sitemap lastmod",
            evidence=f"invalid_lastmod_count={invalid_count}, total_with_lastmod={total}",
            detail=(
                f"{invalid_count} sitemap entries have invalid or unparseable "
                f"lastmod dates. Sitemap lastmod should use W3C Datetime format "
                f"(e.g., 2024-01-15 or 2024-01-15T09:30:00+00:00)."
            ),
            severity=Severity.WARNING,
            confidence=0.9,
        ))

    # Check 2: Future dates
    if future_count > 0:
        findings.append(_mk(
            rule=rule, url=site_url,
            detected=f"{future_count} sitemap entries have future lastmod dates",
            expected="lastmod should not be in the future",
            evidence=f"future_lastmod_count={future_count}, total={total}",
            detail=(
                f"{future_count} sitemap entries have lastmod dates in the future. "
                f"This is typically a server clock or CMS configuration issue."
            ),
            severity=Severity.WARNING,
            confidence=0.95,
        ))

    # Check 3: All same date (suspicious mass-refresh)
    if dates:
        date_counter = Counter(d["date"].strftime("%Y-%m-%d") for d in dates)
        most_common_date, most_common_count = date_counter.most_common(1)[0]
        same_date_ratio = most_common_count / len(dates) if dates else 0

        if same_date_ratio >= 0.9 and len(dates) >= 5:
            today_str = now.strftime("%Y-%m-%d")
            if most_common_date == today_str:
                detail_msg = (
                    f"{most_common_count}/{len(dates)} sitemap URLs ({same_date_ratio:.0%}) "
                    f"have lastmod = today ({most_common_date}). This may indicate a CMS "
                    f"that updates all lastmod values on every publish, which reduces "
                    f"lastmod usefulness for crawl scheduling."
                )
                severity = Severity.WARNING
            else:
                detail_msg = (
                    f"{most_common_count}/{len(dates)} sitemap URLs ({same_date_ratio:.0%}) "
                    f"share the same lastmod date ({most_common_date}). This may be "
                    f"legitimate if all content was published together, but could also "
                    f"indicate a CMS issue."
                )
                severity = Severity.OPPORTUNITY

            findings.append(_mk(
                rule=rule, url=site_url,
                detected=f"High same-date ratio: {same_date_ratio:.0%} = {most_common_date}",
                expected="Diverse lastmod dates reflecting actual content updates",
                evidence=(
                    f"same_date={most_common_date}, "
                    f"same_date_count={most_common_count}, "
                    f"total_dates={len(dates)}, "
                    f"same_date_ratio={same_date_ratio:.3f}"
                ),
                detail=detail_msg,
                severity=severity,
                confidence=0.85,
            ))

    return findings


def _extract_sitemap_urls(data: dict) -> list:
    """Extract sitemap URL entries from available data sources."""
    # Try multiple paths where sitemap data might be
    for key in ["sitemap_urls", "sitemap_entries", "sitemap_data"]:
        val = data.get(key)
        if isinstance(val, list):
            return val
        if isinstance(val, dict):
            urls = val.get("urls") or val.get("entries") or []
            if isinstance(urls, list) and urls:
                return urls

    # Try extended_checks
    ext = data.get("extended_checks", {})
    if isinstance(ext, dict):
        sm = ext.get("sitemap") or ext.get("sitemap_data") or {}
        if isinstance(sm, dict):
            urls = sm.get("urls") or sm.get("entries") or []
            if isinstance(urls, list) and urls:
                return urls
        elif isinstance(sm, list):
            return sm

    return []


def _parse_lastmod(date_str: str) -> Optional[datetime]:
    """Parse a lastmod string into a datetime. Returns None if unparseable."""
    if not date_str or not date_str.strip():
        return None
    date_str = date_str.strip()

    # Try common W3C Datetime formats
    formats = [
        "%Y-%m-%dT%H:%M:%S%z",      # 2024-01-15T09:30:00+00:00
        "%Y-%m-%dT%H:%M:%SZ",        # 2024-01-15T09:30:00Z
        "%Y-%m-%dT%H:%M:%S",         # 2024-01-15T09:30:00
        "%Y-%m-%dT%H:%M%z",          # 2024-01-15T09:30+00:00
        "%Y-%m-%d",                  # 2024-01-15
        "%Y-%m-%d %H:%M:%S",         # 2024-01-15 09:30:00
        "%d/%m/%Y",                  # 15/01/2024
        "%m/%d/%Y",                  # 01/15/2024
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            # Handle timezone-naive: assume UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    # Try ISO 8601 with variable precision
    try:
        from datetime import datetime as dt_class
        # Python 3.7+ supports fromisoformat
        dt = dt_class.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        pass

    return None


# ============================================================
# Rule 47 — Crawlable <a href> (Event-Only Navigation)
# ============================================================

def check_crawlable_links(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 47: Detect interactive navigation elements that lack crawlable
    <a href> anchors.

    Uses existing HTML from crawl export. Checks for onc click handlers,
    data-href patterns, and router-based navigation without proper <a> tags.

    Does NOT flag:
      - Modal openers (not navigation)
      - Form submit buttons
      - Accordion toggles

    Only flags elements that appear to be navigation targets.

    Returns:
        List of Finding objects, one per page with issues.
    """
    findings: list[Finding] = []

    for ctx in page_contexts:
        if ctx.status_code != 200:
            continue

        url = ctx.url
        raw = getattr(ctx, "_raw_export", None) or {}
        page_html = raw.get("html") or raw.get("body") or raw.get("content") or ""
        if not page_html:
            continue

        issues = _analyze_navigation_elements(page_html)
        if not issues:
            continue

        crawlable_count = issues["crawlable_anchor_count"]
        event_only_count = issues["event_only_count"]
        total_interactive = issues["total"]

        if event_only_count == 0:
            continue

        examples = issues["examples"][:3]
        examples_str = " | ".join(examples)

        # Only flag if event-only is a significant fraction
        ratio = event_only_count / total_interactive if total_interactive > 0 else 0

        if ratio >= 0.2 and event_only_count >= 2:
            severity = Severity.WARNING
        elif event_only_count >= 1:
            severity = Severity.OPPORTUNITY
        else:
            continue

        findings.append(_mk(
            rule=rule, url=url,
            detected=(
                f"{event_only_count} navigation elements lack crawlable <a href> "
                f"(of {total_interactive} interactive elements)"
            ),
            expected="Navigation links should use standard <a href> for crawlability",
            evidence=(
                f"crawlable_anchor_count={crawlable_count}, "
                f"event_only_navigation_count={event_only_count}, "
                f"total_interactive={total_interactive}, "
                f"examples=[{examples_str}]"
            ),
            detail=(
                f"Found {event_only_count} navigation elements on {url} that use "
                f"JavaScript events (onclick, router) without a crawlable <a href>. "
                f"This may prevent search engines from discovering linked pages. "
                f"Examples: {examples_str}. "
                f"Total interactive elements: {total_interactive} "
                f"({crawlable_count} with proper <a href>)."
            ),
            severity=severity,
            confidence=0.75,
        ))

    return findings


def _analyze_navigation_elements(html: str) -> dict:
    """Analyze HTML for navigation elements with/without crawlable anchors.

    Returns:
        Dict with crawlable_anchor_count, event_only_count, total, examples.
    """
    result = {
        "crawlable_anchor_count": 0,
        "event_only_count": 0,
        "total": 0,
        "examples": [],
    }

    # Find all <a> tags with onclick navigation (but NOT modal/accordion)
    onclick_nav_pattern = re.compile(
        r'<a\s[^>]*\bonclick\s*=\s*["\']\s*(?:location\.href|window\.location|location\.replace|window\.open|document\.location)\s*[=\.]',
        re.IGNORECASE,
    )
    # Find <a> tags with href
    href_pattern = re.compile(r'<a\s[^>]*\bhref\s*=\s*["\'][^"\'>]+["\']', re.IGNORECASE)

    # Find elements with data-href or router-link without wrapping <a>
    data_href_pattern = re.compile(
        r'<(?:div|span|li|button|card)\s[^>]*\bdata-href\s*=\s*["\']([^"\']+)["\']',
        re.IGNORECASE,
    )

    # Count crawlable anchors
    crawlable_matches = href_pattern.findall(html)
    result["crawlable_anchor_count"] = len(crawlable_matches)

    # Find onc lick navigation (not modal/form/accordion)
    onclick_matches = onclick_nav_pattern.findall(html)
    result["event_only_count"] = len(onclick_matches)

    # Find data-href elements
    data_href_matches = data_href_pattern.findall(html)
    result["event_only_count"] += len(data_href_matches)

    result["total"] = (
        result["crawlable_anchor_count"] + result["event_only_count"]
    )

    # Collect examples
    for m in onclick_matches[:3]:
        snippet = m[:100] if isinstance(m, str) else str(m)[:100]
        result["examples"].append(f"onclick-nav: {snippet}...")
    for m in data_href_matches[:3]:
        result["examples"].append(f"data-href without <a>: {m}")

    return result


# ============================================================
# Rule 51 — Internal Links → Redirect URLs
# ============================================================

def check_internal_redirect_links(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 51: Detect internal links that point to redirect URLs (3xx).

    Uses link graph + page status map to find internal <a href> links
    pointing to URLs that return 301/302/307/308.

    Builds a URL→status lookup map first (O(1) per link), avoiding O(n^2).

    Returns:
        List of Finding objects, one per redirect link found.
    """
    findings: list[Finding] = []

    # Build URL → (status_code, final_url) lookup map
    url_status_map: dict[str, tuple[int, Optional[str]]] = {}
    for ctx in page_contexts:
        normalized = ctx.url.rstrip("/").lower()
        url_status_map[normalized] = (ctx.status_code, ctx.canonical_url or ctx.url)
        # Also map with trailing slash
        url_status_map[normalized + "/"] = (ctx.status_code, ctx.canonical_url or ctx.url)

    redirect_codes = {301, 302, 307, 308}
    redirect_pages = {
        url: (status, final)
        for url, (status, final) in url_status_map.items()
        if status in redirect_codes
    }
    broken_pages = {
        url: status
        for url, (status, _) in url_status_map.items()
        if status >= 400
    }

    # Scan all internal links
    for ctx in page_contexts:
        if ctx.status_code != 200:
            continue

        source_url = ctx.url
        links = ctx.links_detailed or []

        for link in links:
            if not isinstance(link, dict):
                continue
            target_url = link.get("url", "")
            is_internal = link.get("is_internal", True)
            anchor = link.get("anchor", "") or link.get("anchor_text", "") or ""

            if not target_url or not is_internal:
                continue

            normalized_target = target_url.rstrip("/").lower()

            # Check redirect
            if normalized_target in redirect_pages:
                status, final_url = redirect_pages[normalized_target]
                findings.append(_mk(
                    rule=rule, url=source_url,
                    detected=f"Internal link to {target_url} returns HTTP {status}",
                    expected="Internal links should point directly to the final 200 URL",
                    evidence=(
                        f"source_url={source_url}, "
                        f"linked_url={target_url}, "
                        f"status={status}, "
                        f"final_url={final_url}, "
                        f"anchor_text={anchor[:80]}"
                    ),
                    detail=(
                        f"Internal link from {source_url} to {target_url} "
                        f"returns HTTP {status} redirect to {final_url}. "
                        f"Update the link to point directly to the final URL "
                        f"to avoid redirect chains and preserve link equity."
                    ),
                    severity=Severity.OPPORTUNITY,
                    confidence=0.95,
                ))
                continue

            # Check broken target
            if normalized_target in broken_pages:
                status = broken_pages[normalized_target]
                findings.append(_mk(
                    rule=rule, url=source_url,
                    detected=f"Internal link to {target_url} returns HTTP {status}",
                    expected="Internal links should point to live (200) URLs",
                    evidence=(
                        f"source_url={source_url}, "
                        f"linked_url={target_url}, "
                        f"status={status}, "
                        f"anchor_text={anchor[:80]}"
                    ),
                    detail=(
                        f"Internal link from {source_url} points to {target_url} "
                        f"which returns HTTP {status}. Fix or remove this link."
                    ),
                    severity=Severity.WARNING,
                    confidence=0.95,
                ))

    return findings


# ============================================================
# Rule 60 — Multi-language Canonical
# ============================================================

def check_multilang_canonical(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 60: Detect cross-language canonical issues.

    Checks if pages with a language-specific path (e.g., /de/, /fr/) have
    a canonical URL pointing to a different language (e.g., /en/).

    Uses URL path language detection, canonical URL comparison, hreflang
    tags, and html lang attribute.

    Does NOT flag same-language regional variants (e.g., /en-us/ → /en-gb/
    canonical when these are regional, not translated).

    Returns:
        List of Finding objects.
    """
    findings: list[Finding] = []

    for ctx in page_contexts:
        if ctx.status_code != 200:
            continue

        url = ctx.url
        canonical = ctx.canonical_url or ""

        if not canonical or canonical == url:
            continue  # Self-canonical — fine

        # Detect page language
        page_lang = _detect_page_language(url, ctx)
        canonical_lang = _detect_url_language(canonical)

        if page_lang is None or canonical_lang is None:
            continue  # Can't determine languages

        if page_lang == canonical_lang:
            continue  # Same language — fine

        # Cross-language canonical detected
        hreflang_langs = _get_hreflang_languages(ctx)

        # Check if this is a legitimate same-language variant
        # (e.g., en-us → en-gb with hreflang cluster)
        if _is_regional_variant(page_lang, canonical_lang, hreflang_langs):
            continue

        evidence = (
            f"page_url={url}, "
            f"page_language={page_lang}, "
            f"canonical_url={canonical}, "
            f"canonical_language={canonical_lang}, "
            f"hreflang_languages={hreflang_langs}, "
            f"html_lang={ctx.lang or ''}"
        )

        findings.append(_mk(
            rule=rule, url=url,
            detected=(
                f"Cross-language canonical: {page_lang} page canonical → "
                f"{canonical_lang} URL ({canonical})"
            ),
            expected=(
                f"Pages with {page_lang} content should use a {page_lang} "
                f"canonical (or self-canonical)"
            ),
            evidence=evidence,
            detail=(
                f"Page at {url} (language: {page_lang}) has canonical URL "
                f"{canonical} (language: {canonical_lang}). "
                f"Per Google's hreflang guidance, localized pages should "
                f"use a self-referencing canonical or a canonical in the "
                f"same language. Hreflang languages: {hreflang_langs or 'none'}."
            ),
            severity=Severity.WARNING,
            confidence=0.85,
        ))

    return findings


def _detect_page_language(url: str, ctx: PageContext) -> Optional[str]:
    """Detect page language from URL path → html lang → hreflang."""
    # 1. URL path language
    lang = _detect_url_language(url)
    if lang:
        return lang
    # 2. HTML lang attribute
    if ctx.lang:
        lang_code = ctx.lang.lower().split("-")[0][:2]
        if lang_code.isalpha() and len(lang_code) == 2:
            return lang_code
    # 3. Hreflang self-reference
    if ctx.hreflang_summary:
        for entry in ctx.hreflang_summary:
            if isinstance(entry, dict) and entry.get("url", "").rstrip("/").lower() == url.rstrip("/").lower():
                lang = entry.get("lang", "")
                if lang and len(lang) >= 2:
                    return lang.lower()[:2]
    return None


def _detect_url_language(url: str) -> Optional[str]:
    """Detect language from URL path prefix (e.g., /en/, /de/)."""
    try:
        path = urlparse(url).path.strip("/")
        if not path:
            return None
        segments = path.split("/")
        first = segments[0].lower()
        if len(first) == 2 and first.isalpha():
            return first
        # Check for locale like en-US
        if len(first) >= 2 and first[:2].isalpha() and "-" in first:
            return first[:2].lower()
    except Exception:
        pass
    return None


def _get_hreflang_languages(ctx: PageContext) -> list[str]:
    """Get list of languages from hreflang tags."""
    langs = []
    if ctx.hreflang_summary:
        for entry in ctx.hreflang_summary:
            if isinstance(entry, dict):
                lang = entry.get("lang", "")
                if lang:
                    langs.append(lang.lower())
    return langs


def _is_regional_variant(
    page_lang: str, canonical_lang: str, hreflang_langs: list[str]
) -> bool:
    """Check if this is a regional variant (same base language, different
    region) rather than truly different languages.

    e.g., en-us → en-gb is regional; de → en is cross-language.
    """
    if page_lang == canonical_lang:
        return True

    # Check hreflang cluster: both page and canonical language codes
    # appear as the same base language
    all_base = set()
    for l in hreflang_langs:
        all_base.add(l.split("-")[0][:2] if "-" in l else l[:2])

    if page_lang in all_base and canonical_lang in all_base:
        # If all hreflang languages share the same base, it's likely regional
        page_base = page_lang.split("-")[0][:2] if "-" in page_lang else page_lang[:2]
        canon_base = canonical_lang.split("-")[0][:2] if "-" in canonical_lang else canonical_lang[:2]
        if page_base == canon_base:
            return True

    return False


# ============================================================
# Rule 67 — Staging / Dev Indexability
# ============================================================

def check_staging_indexability(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 67: Detect staging/dev environment indexability.

    Checks:
      A. Current audit hostname matches staging/dev patterns
      B. Staging/dev URLs found in crawl/link/sitemap/canonical/hreflang data
      C. User-configured STAGING_URLS

    Does NOT:
      - Brute-force subdomain enumeration
      - Scan DNS
      - Guess dev/staging hostnames

    Returns:
        List of Finding objects.
    """
    findings: list[Finding] = []
    site_url = site_ctx.base_url or ""
    parsed_site = urlparse(site_url) if site_url else None
    site_hostname = parsed_site.hostname or "" if parsed_site else ""

    # Check A: Current audit hostname is staging/dev
    if site_hostname and _is_staging_hostname(site_hostname):
        # Check if indexable
        homepage_indexable = False
        for ctx in page_contexts:
            path = urlparse(ctx.url).path if ctx.url else ""
            if path in ("", "/") and ctx.status_code == 200:
                homepage_indexable = _is_indexable(ctx)
                break

        if homepage_indexable:
            findings.append(_mk(
                rule=rule, url=site_url,
                detected=(
                    f"Staging/dev hostname ({site_hostname}) is indexable "
                    f"with no access restriction"
                ),
                expected="Staging/dev environments should be noindex, password-protected, or blocked by robots.txt",
                evidence=(
                    f"hostname={site_hostname}, "
                    f"matches_staging_pattern=true, "
                    f"indexable=true"
                ),
                detail=(
                    f"CRITICAL: The current audit hostname '{site_hostname}' "
                    f"matches known staging/development patterns and appears to be "
                    f"publicly indexable. This risks duplicate content issues and "
                    f"confidential data exposure in search results. "
                    f"Immediately add noindex or password protection."
                ),
                severity=Severity.ERROR,
                confidence=0.95,
            ))

    # Check B: Staging URLs found in crawl data
    staging_candidates = _find_staging_candidates(site_hostname, page_contexts, data)

    # Check C: User-configured staging URLs
    user_staging = data.get("STAGING_URLS", [])
    if isinstance(user_staging, str):
        user_staging = [u.strip() for u in user_staging.split(",") if u.strip()]
    if isinstance(user_staging, list):
        for u in user_staging:
            staging_candidates.append({
                "url": u,
                "source": "user_config",
                "indexable": None,  # Unknown — can't verify
            })

    if not staging_candidates and not (
        site_hostname and _is_staging_hostname(site_hostname)
    ):
        # No staging candidates found — NOT_CHECKED (not PASS)
        findings.append(_mk(
            rule=rule, url=site_url,
            detected="No staging/dev candidates detected from available data",
            expected="Staging/dev environments should be noindex if they exist",
            evidence="staging_candidates=0, hostname_check=clean",
            detail=(
                "No staging or development environment URLs were found in "
                "the crawl, link graph, sitemap, or canonical/hreflang data. "
                "This does NOT guarantee no staging environment exists — "
                "only that none was discovered from available signals."
            ),
            severity=Severity.INFO,
            confidence=0.4,  # Low confidence — can't prove absence
        ))
        return findings

    # Report each staging candidate
    for candidate in staging_candidates:
        candidate_url = candidate.get("url", "")
        source = candidate.get("source", "unknown")
        idx = candidate.get("indexable", None)

        if idx is True:
            severity = Severity.ERROR
            detail = (
                f"Staging/dev URL {candidate_url} (found via {source}) "
                f"appears to be indexable. Add noindex or password protection."
            )
        elif idx is False:
            continue  # Already protected — no finding needed
        else:
            severity = Severity.WARNING
            detail = (
                f"Potential staging/dev URL {candidate_url} (found via {source}). "
                f"Verify it is not indexable. Indexability status unknown."
            )

        findings.append(_mk(
            rule=rule, url=candidate_url,
            detected=f"Staging/dev candidate from {source}: {candidate_url}",
            expected="Staging/dev environments should be noindex, password-protected, or blocked by robots.txt",
            evidence=f"candidate_source={source}, candidate_url={candidate_url}",
            detail=detail,
            severity=severity,
            confidence=0.8 if idx is True else 0.5,
        ))

    return findings


def _is_staging_hostname(hostname: str) -> bool:
    """Check if hostname matches known staging/dev patterns."""
    hostname_lower = hostname.lower()
    for pattern in _STAGING_HOSTNAME_PATTERNS:
        if pattern.search(hostname_lower):
            return True
    return False


def _find_staging_candidates(
    site_hostname: str, page_contexts: list[PageContext], data: dict
) -> list[dict]:
    """Find staging/dev URLs from crawl, links, sitemap, canonical, hreflang."""
    candidates = []
    seen = set()

    site_domain = ""
    try:
        site_domain = urlparse(f"http://{site_hostname}").hostname or ""
        # Extract root domain
        parts = site_domain.split(".")
        if len(parts) >= 2:
            site_domain = ".".join(parts[-2:])
    except Exception:
        pass

    for ctx in page_contexts:
        # Check page URL itself
        if _check_url_for_staging(ctx.url, site_hostname, site_domain, seen):
            candidates.append({
                "url": ctx.url,
                "source": "crawl_page",
                "indexable": _is_indexable(ctx) and ctx.status_code == 200,
            })

        # Check canonical
        if ctx.canonical_url:
            if _check_url_for_staging(ctx.canonical_url, site_hostname, site_domain, seen):
                candidates.append({
                    "url": ctx.canonical_url,
                    "source": "canonical",
                    "indexable": None,
                })

        # Check hreflang URLs
        if ctx.hreflang_summary:
            for entry in ctx.hreflang_summary:
                if isinstance(entry, dict):
                    h_url = entry.get("url", "")
                    if _check_url_for_staging(h_url, site_hostname, site_domain, seen):
                        candidates.append({
                            "url": h_url,
                            "source": "hreflang",
                            "indexable": None,
                        })

        # Check internal links for staging domains
        if ctx.links_detailed:
            for link in ctx.links_detailed:
                if isinstance(link, dict):
                    l_url = link.get("url", "")
                    if _check_url_for_staging(l_url, site_hostname, site_domain, seen):
                        candidates.append({
                            "url": l_url,
                            "source": "internal_link",
                            "indexable": None,
                        })

    return candidates


def _check_url_for_staging(
    url: str, site_hostname: str, site_domain: str, seen: set
) -> bool:
    """Check if a URL points to a staging/dev hostname. Returns True and adds to seen."""
    if not url:
        return False
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False

    if not host:
        return False

    # Skip same-host URLs
    if host.lower() == site_hostname.lower():
        return False

    # Check for staging patterns
    if _is_staging_hostname(host):
        key = host.lower()
        if key not in seen:
            seen.add(key)
            return True

    return False
