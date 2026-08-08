"""Crawl-evidence checks for previously unbound EXISTING_PARTIAL rules."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import re
from urllib.parse import parse_qsl, urlsplit

from audit_rules.adapters import DataUnavailableError, PartialExecutionError
from audit_rules.context import PageContext, SiteContext
from audit_rules.models import Finding, RuleDefinition


def _finding(
    rule: RuleDefinition,
    *,
    url: str,
    detected: str,
    expected: str,
    evidence: str,
    severity: str | None = None,
    confidence: float = 1.0,
) -> Finding:
    return Finding(
        audit_id=rule.audit_id,
        rule_id=rule.rule_id,
        url=url,
        category=rule.category.value,
        priority=rule.priority.value,
        severity=severity or rule.severity.value,
        finding_type=rule.default_finding_type,
        scope=rule.scope.value,
        detected_value=detected,
        expected_value=expected,
        evidence=evidence,
        finding_detail=f"{detected}. {evidence}",
        remediation=rule.remediation,
        owner=rule.owner,
        acceptance_criteria=rule.acceptance_criteria,
        data_source="LibreCrawl",
        confidence=confidence,
    )


def check_xml_sitemap_valid(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 2 local evidence: sitemap existence and crawled URL health."""
    if not site_ctx.sitemap_found:
        return [_finding(
            rule,
            url=site_ctx.base_url or "SITE",
            detected="XML sitemap not found",
            expected="A readable XML sitemap containing canonical indexable URLs",
            evidence="sitemap_found=False",
            severity="Error",
        )]

    findings: list[Finding] = []
    raw_sitemap = (site_ctx._site_data or {}).get("sitemap", {}) or {}
    count_was_exported = "url_count" in raw_sitemap
    if count_was_exported and site_ctx.sitemap_url_count <= 0:
        findings.append(_finding(
            rule,
            url=site_ctx.sitemap_url or site_ctx.base_url or "SITE",
            detected="Sitemap contains zero URLs",
            expected="Sitemap contains important canonical URLs",
            evidence=f"sitemap_url_count={site_ctx.sitemap_url_count}",
            severity="Warning",
        ))

    sitemap_items = raw_sitemap.get("urls", []) or []
    sitemap_urls = {
        item.get("url", item.get("loc", "")) if isinstance(item, dict) else str(item)
        for item in sitemap_items
    }
    sitemap_urls.discard("")
    page_by_url = {page.url: page for page in page_contexts}
    for url in sorted(sitemap_urls):
        page = page_by_url.get(url)
        if page is None:
            continue
        if page.status_code != 200:
            findings.append(_finding(
                rule,
                url=url,
                detected=f"Sitemap URL returns HTTP {page.status_code}",
                expected="Sitemap URLs return HTTP 200",
                evidence=f"sitemap_member=True; status_code={page.status_code}",
                severity="Error",
            ))
            continue
        if "noindex" in (page.robots or "").lower():
            findings.append(_finding(
                rule,
                url=url,
                detected="Sitemap URL is noindex",
                expected="Sitemap URLs are indexable",
                evidence=f"sitemap_member=True; robots={page.robots}",
                severity="Error",
            ))
        canonical = (page.canonical_url or "").rstrip("/")
        if canonical and canonical != url.rstrip("/"):
            findings.append(_finding(
                rule,
                url=url,
                detected="Sitemap URL canonicalizes elsewhere",
                expected="Sitemap URL is self-canonical",
                evidence=f"canonical={page.canonical_url}",
                severity="Warning",
            ))
    return findings


_SESSION_PARAMS = {
    "phpsessid", "jsessionid", "sid", "sessionid", "session_id", "aspsessionid",
}
_FACET_PARAMS = {
    "color", "size", "brand", "sort", "order", "filter", "price", "material",
    "page", "view", "rating",
}


def check_crawl_budget_waste(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 5 local evidence: deterministic wasteful URL-space patterns."""
    findings: list[Finding] = []
    current_year = datetime.now().year
    for page in page_contexts:
        parsed = urlsplit(page.url)
        params = [(key.lower(), value) for key, value in parse_qsl(parsed.query)]
        names = [key for key, _ in params]
        evidence: list[str] = []
        if any(name in _SESSION_PARAMS for name in names):
            evidence.append("session_parameter")
        year_values = [value for name, value in params if name in {"year", "yyyy", "date"}]
        if any(value[:4].isdigit() and int(value[:4]) > current_year + 1 for value in year_values):
            evidence.append("future_calendar")
        if re.search(r"/(?:search|s)/?$", parsed.path, re.IGNORECASE) or any(
            name in {"q", "query", "search", "s"} for name in names
        ):
            evidence.append("internal_search")
        facet_count = sum(1 for name in names if name in _FACET_PARAMS)
        if facet_count >= 4:
            evidence.append(f"faceted_parameter_count={facet_count}")
        if len(params) >= 6:
            evidence.append(f"high_parameter_count={len(params)}")
        if evidence:
            findings.append(_finding(
                rule,
                url=page.url,
                detected="Potential crawl-budget waste URL",
                expected="Finite, intentional crawlable URL space",
                evidence="; ".join(evidence),
                severity="Warning",
                confidence=0.9,
            ))
    return findings


def _estimate_title_width(title: str) -> int:
    """Estimate rendered title width without pretending to be a browser."""
    width = 0
    for char in title:
        if char in "WwMm@%&":
            width += 11
        elif char in "ilI1.,'|! ":
            width += 4
        elif ord(char) > 0x2E80:
            width += 14
        else:
            width += 7
    return width


def check_title_uniqueness(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 13 local evidence: missing, duplicate, and likely truncating titles."""
    findings: list[Finding] = []
    titles: dict[str, list[PageContext]] = defaultdict(list)
    for page in page_contexts:
        if page.status_code != 200:
            continue
        title = " ".join((page.title or "").split())
        if not title:
            findings.append(_finding(
                rule, url=page.url, detected="Missing title",
                expected="A unique descriptive title", evidence="title=''",
                severity="Error",
            ))
            continue
        titles[title.casefold()].append(page)
        estimated_width = _estimate_title_width(title)
        if estimated_width > 580:
            findings.append(_finding(
                rule,
                url=page.url,
                detected=f"Estimated title width {estimated_width}px",
                expected="Title likely fits the SERP display without severe truncation",
                evidence=f"estimated_width_px={estimated_width}; chars={len(title)}",
                severity="Opportunity",
                confidence=0.75,
            ))

    for group in titles.values():
        if len(group) < 2:
            continue
        title = " ".join((group[0].title or "").split())
        for page in group:
            findings.append(_finding(
                rule,
                url=page.url,
                detected=f"Duplicate title shared by {len(group)} pages",
                expected="Unique title per indexable page",
                evidence=f"title={title!r}; duplicate_count={len(group)}",
                severity="Warning",
            ))
    return findings


def _headers(page: PageContext) -> dict[str, str] | None:
    raw = page.response_headers
    if not isinstance(raw, dict) or not raw:
        return None
    return {str(key).lower(): str(value) for key, value in raw.items()}


def check_cache_cdn(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 23: inspect exported cache and CDN response headers."""
    header_pages = [(page, _headers(page)) for page in page_contexts if page.status_code == 200]
    available = [(page, headers) for page, headers in header_pages if headers is not None]
    if not available:
        raise DataUnavailableError("Response headers absent from crawl export")

    findings: list[Finding] = []
    for page, headers in available:
        cache_control = headers.get("cache-control", "")
        if not cache_control:
            findings.append(_finding(
                rule,
                url=page.url,
                detected="No Cache-Control policy exported",
                expected="An explicit cache policy appropriate to the page",
                evidence="cache-control=missing",
                severity="Warning",
            ))
        elif "no-store" in cache_control.lower() and not _is_dynamic_url(page.url):
            findings.append(_finding(
                rule,
                url=page.url,
                detected="Anonymous page uses no-store",
                expected="Cacheable anonymous content has an explicit max-age policy",
                evidence=f"cache-control={cache_control}",
                severity="Opportunity",
            ))
    missing_count = len(header_pages) - len(available)
    if missing_count:
        raise PartialExecutionError(
            f"Response headers available for {len(available)}/{len(header_pages)} eligible pages",
            findings,
        )
    return findings


_MIXED_RESOURCE_RE = re.compile(
    r"(?:src|data-src|poster)\s*=\s*['\"]http://",
    re.IGNORECASE,
)


def check_https_certificate(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 25: HTTPS coverage, mixed resources, and optional TLS evidence."""
    findings: list[Finding] = []
    if not site_ctx.https_redirects:
        findings.append(_finding(
            rule,
            url=site_ctx.base_url or "SITE",
            detected="HTTP does not reliably redirect to HTTPS",
            expected="All HTTP requests redirect to the canonical HTTPS host",
            evidence="https_redirects=False",
            severity="Error",
        ))
    for page in page_contexts:
        if urlsplit(page.url).scheme.lower() == "http":
            findings.append(_finding(
                rule,
                url=page.url,
                detected="Crawled page remains on HTTP",
                expected="Every crawled page uses HTTPS",
                evidence="page_scheme=http",
                severity="Error",
            ))
        raw = page._raw_export or {}
        mixed = raw.get("mixed_content") or raw.get("mixed_content_urls") or []
        html = page.body_html or ""
        if mixed or _MIXED_RESOURCE_RE.search(html):
            findings.append(_finding(
                rule,
                url=page.url,
                detected="Mixed-content resource on HTTPS page",
                expected="All page resources use HTTPS",
                evidence=f"mixed_content={len(mixed) if isinstance(mixed, list) else 1}",
                severity="Error",
            ))

    tls = (site_ctx._site_data or {}).get("tls_certificate")
    if isinstance(tls, dict):
        valid = tls.get("valid")
        days = tls.get("days_remaining")
        if valid is False:
            findings.append(_finding(
                rule,
                url=site_ctx.base_url or "SITE",
                detected="TLS certificate is invalid",
                expected="A valid complete certificate chain",
                evidence=f"tls_valid=False; days_remaining={days}",
                severity="Error",
            ))
        elif isinstance(days, (int, float)) and days < 30:
            findings.append(_finding(
                rule,
                url=site_ctx.base_url or "SITE",
                detected=f"TLS certificate expires in {days} days",
                expected="Certificate auto-renewal with more than 30 days remaining",
                evidence=f"tls_valid={valid}; days_remaining={days}",
                severity="Warning",
            ))
    return findings


_DYNAMIC_PATH_RE = re.compile(
    r"/(?:cart|checkout|my-account|account|login|wp-admin|wp-login|form)(?:/|$)",
    re.IGNORECASE,
)


def _is_dynamic_url(url: str) -> bool:
    return bool(_DYNAMIC_PATH_RE.search(urlsplit(url).path))


def check_cache_plugin_cdn_synergy(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 66: detect dangerous public caching of WordPress dynamic pages."""
    eligible = [(page, _headers(page)) for page in page_contexts if page.status_code == 200]
    available = [(page, headers) for page, headers in eligible if headers is not None]
    if not available:
        raise DataUnavailableError("Response headers absent from crawl export")

    findings: list[Finding] = []
    for page, headers in available:
        if not _is_dynamic_url(page.url):
            continue
        cache_control = headers.get("cache-control", "").lower()
        cache_status = (
            headers.get("cf-cache-status")
            or headers.get("x-cache")
            or ""
        ).upper()
        publicly_cacheable = "public" in cache_control and "no-store" not in cache_control
        cache_hit = "HIT" in cache_status
        if publicly_cacheable or cache_hit:
            findings.append(_finding(
                rule,
                url=page.url,
                detected="Dynamic WordPress page is publicly cached",
                expected="Cart/login/account/form pages bypass shared caches",
                evidence=(
                    f"cache-control={cache_control}; cache_status={cache_status}; "
                    "dynamic_page=True"
                ),
                severity="Error",
            ))
    missing_count = len(eligible) - len(available)
    if missing_count:
        raise PartialExecutionError(
            f"Response headers available for {len(available)}/{len(eligible)} eligible pages",
            findings,
        )
    return findings
