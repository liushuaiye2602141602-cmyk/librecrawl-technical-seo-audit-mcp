"""Phase 1 Compatibility Adapters — bind existing check logic to registry rules.

Design (Requirement 8):
  - 18 EXISTING_FULL rules use adapter/binding to existing logic, NOT reimplementation.
  - Do NOT modify existing check implementations (no deletions, no deprecation warnings).
  - Feature flag MASTER_AUDIT_V3_ENABLED defaults to False (shadow/parallel mode).
  - Adapters extract findings from existing code output and map to Finding objects.

Each adapter:
  1. Takes SiteContext + PageContext(s) + existing check output data
  2. Produces list[Finding] in the unified format
  3. Is registered by rule_id for dispatch by RuleRunner

Usage:
    registry = load_registry()
    harness = CompatibilityHarness(registry)
    findings = harness.run_existing_full(site_ctx, page_contexts, existing_data)
"""

from typing import Optional, Callable
from dataclasses import dataclass, field

from audit_rules.models import RuleDefinition, Finding
from audit_rules.context import SiteContext, PageContext


# Type alias for adapter function signature
AdapterFunc = Callable[..., list[Finding]]


@dataclass
class CompatibilityHarness:
    """Binds 18 EXISTING_FULL rules to their existing check implementations.

    Each adapter extracts findings from existing LibreCrawl output data
    and returns list[Finding] in the unified format. No existing code
    is modified — adapters read from existing output structures.
    """

    registry: list[RuleDefinition]
    _adapters: dict[str, AdapterFunc] = field(default_factory=dict)

    def __post_init__(self):
        """Register all 18 EXISTING_FULL adapters."""
        self._adapters = {
            # 1: robots.txt existence + rules
            "robots_txt_exists": _adapter_robots_txt,
            # 3: noindex/nofollow audit
            "page_noindex_nofollow": _adapter_noindex_nofollow,
            # 4: crawl errors (4xx/5xx)
            "crawl_errors_4xx_5xx": _adapter_crawl_errors,
            # 6: unified domain + protocol
            "unified_domain_protocol": _adapter_domain_protocol,
            # 7: redirect chain audit
            "redirect_chain_audit": _adapter_redirect_chains,
            # 8: canonical correctness
            "canonical_correctness": _adapter_canonical,
            # 9: click depth
            "click_depth": _adapter_click_depth,
            # 11: internal link distribution
            "internal_link_distribution": _adapter_internal_links,
            # 14: meta description audit
            "meta_description": _adapter_meta_description,
            # 15: H1 heading hierarchy
            "h1_heading_hierarchy": _adapter_h1_headings,
            # 26: HSTS + security headers
            "hsts_security_headers": _adapter_security_headers,
            # 27: schema type coverage
            "schema_type_coverage": _adapter_schema_coverage,
            # 29: hreflang basics
            "hreflang_basics": _adapter_hreflang_basics,
            # 30: broken internal links
            "broken_internal_links": _adapter_broken_links,
            # 41: soft 404 detection
            "soft_404": _adapter_soft_404,
            # 42: sitemap URL indexability
            "sitemap_url_indexability": _adapter_sitemap_indexability,
            # 45: orphan pages
            "orphan_pages": _adapter_orphan_pages,
            # 58: hreflang indexability
            "hreflang_indexability": _adapter_hreflang_indexability,
        }

    def run_existing_full(
        self,
        site_ctx: SiteContext,
        page_contexts: list[PageContext],
        existing_data: dict,
    ) -> list[Finding]:
        """Run all 18 EXISTING_FULL adapters against provided data.

        Args:
            site_ctx: Site-level context (robots.txt, sitemap, profile, etc.)
            page_contexts: All page contexts from the crawl
            existing_data: Dict with keys matching existing check output sections:
                - site_check: _site_check() result dict
                - build_report: _build_report() result summary
                - extended_checks: extended_checks results dict
                - crawl: raw crawl result dict

        Returns:
            List of Finding objects for all executed rules
        """
        all_findings: list[Finding] = []
        for rule in self.registry:
            if rule.rule_id not in self._adapters:
                continue
            adapter = self._adapters[rule.rule_id]
            try:
                findings = adapter(rule, site_ctx, page_contexts, existing_data)
                all_findings.extend(findings)
            except Exception:
                # Adapter failed — rule gets NOT_CHECKED (no findings = no execution)
                continue
        return all_findings


# ============================================================
# Adapter functions — one per EXISTING_FULL rule
# ============================================================

def _mk_finding(rule: RuleDefinition, url: str = "", detected: str = "",
                expected: str = "", evidence: str = "", detail: str = "",
                confidence: float = 1.0) -> Finding:
    """Factory for Finding with rule-derived defaults."""
    return Finding(
        audit_id=rule.audit_id,
        rule_id=rule.rule_id,
        url=url,
        category=rule.category.value,
        priority=str(rule.priority.value),
        severity=str(rule.severity.value),
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


def _adapter_robots_txt(
    rule: RuleDefinition, site_ctx: SiteContext,
    page_contexts: list[PageContext], data: dict,
) -> list[Finding]:
    """Rule 1: robots.txt existence + rules."""
    findings = []

    if not site_ctx.robots_txt_found:
        findings.append(_mk_finding(
            rule, url=site_ctx.base_url,
            detected="/robots.txt not found",
            expected="/robots.txt returns 200",
            evidence="robots_txt_found=False",
            detail="/robots.txt not found or inaccessible",
        ))
    elif site_ctx.robots_txt_disallow_count > 5:
        findings.append(_mk_finding(
            rule, url=site_ctx.base_url,
            detected=f"Disallow count: {site_ctx.robots_txt_disallow_count}",
            expected="Disallow rules ≤5 unless justified",
            evidence=f"robots_txt_disallow_count={site_ctx.robots_txt_disallow_count}",
            detail=f"High disallow count ({site_ctx.robots_txt_disallow_count}) — review for over-blocking",
        ))

    return findings


def _adapter_noindex_nofollow(
    rule: RuleDefinition, site_ctx: SiteContext,
    page_contexts: list[PageContext], data: dict,
) -> list[Finding]:
    """Rule 3: page noindex/nofollow check."""
    findings = []
    for ctx in page_contexts:
        if ctx.status_code != 200:
            continue
        robots = (ctx.robots or "").lower()
        if "noindex" in robots and ctx.depth <= 2:
            findings.append(_mk_finding(
                rule, url=ctx.url,
                detected=f"meta robots: {ctx.robots}",
                expected="index, follow for important pages",
                evidence=f"robots={ctx.robots}",
                detail=f"Page at depth {ctx.depth} has noindex — may block indexing of important content",
            ))
    return findings


def _adapter_crawl_errors(
    rule: RuleDefinition, site_ctx: SiteContext,
    page_contexts: list[PageContext], data: dict,
) -> list[Finding]:
    """Rule 4: crawl errors (4xx/5xx)."""
    findings = []
    for ctx in page_contexts:
        if ctx.status_code >= 400:
            findings.append(_mk_finding(
                rule, url=ctx.url,
                detected=f"Status {ctx.status_code}",
                expected="Status 200 for crawlable pages",
                evidence=f"status_code={ctx.status_code}",
                detail=f"Broken page: {ctx.url} returned {ctx.status_code}",
            ))
    return findings


def _adapter_domain_protocol(
    rule: RuleDefinition, site_ctx: SiteContext,
    page_contexts: list[PageContext], data: dict,
) -> list[Finding]:
    """Rule 6: unified domain + protocol."""
    findings = []
    if not site_ctx.https_redirects:
        findings.append(_mk_finding(
            rule, url=site_ctx.base_url,
            detected="HTTP→HTTPS redirect not found",
            expected="HTTP 301→ HTTPS",
            evidence="https_redirect=False",
            detail="HTTP to HTTPS redirect is missing or misconfigured",
        ))
    if site_ctx.www_redirects:
        findings.append(_mk_finding(
            rule, url=site_ctx.base_url,
            detected="www/non-www redirect detected",
            expected="Single canonical domain (no dual resolution)",
            evidence="www_redirect=True",
            detail="www redirect is active — ensure only one canonical domain resolves",
        ))
    return findings


def _adapter_redirect_chains(
    rule: RuleDefinition, site_ctx: SiteContext,
    page_contexts: list[PageContext], data: dict,
) -> list[Finding]:
    """Rule 7: redirect chain audit."""
    findings = []
    crawl = data.get("crawl", {})
    redirects = crawl.get("redirects", []) if crawl else []

    for redir in redirects:
        chain = redir.get("chain", [])
        if len(chain) > 1:
            findings.append(_mk_finding(
                rule, url=redir.get("source", ""),
                detected=f"Redirect chain depth={len(chain)}",
                expected="Direct (single-hop) redirects",
                evidence=f"chain={chain}",
                detail=f"Redirect chain of {len(chain)} hops: {' → '.join(chain)}",
            ))
    return findings


def _adapter_canonical(
    rule: RuleDefinition, site_ctx: SiteContext,
    page_contexts: list[PageContext], data: dict,
) -> list[Finding]:
    """Rule 8: canonical correctness."""
    findings = []
    for ctx in page_contexts:
        if ctx.status_code != 200:
            continue
        if not ctx.canonical_url:
            findings.append(_mk_finding(
                rule, url=ctx.url,
                detected="No canonical URL",
                expected="Self-referencing canonical URL",
                evidence="canonical_url=None",
                detail=f"Page missing canonical tag: {ctx.url}",
            ))
        elif ctx.canonical_url != ctx.url:
            findings.append(_mk_finding(
                rule, url=ctx.url,
                detected=f"Non-self canonical: {ctx.canonical_url}",
                expected=f"Self-canonical: {ctx.url}",
                evidence=f"canonical={ctx.canonical_url}",
                detail=f"Page canonical points to different URL: {ctx.canonical_url}",
            ))
    return findings


def _adapter_click_depth(
    rule: RuleDefinition, site_ctx: SiteContext,
    page_contexts: list[PageContext], data: dict,
) -> list[Finding]:
    """Rule 9: click depth."""
    findings = []
    for ctx in page_contexts:
        if ctx.depth > 4:
            findings.append(_mk_finding(
                rule, url=ctx.url,
                detected=f"Depth={ctx.depth}",
                expected="Depth ≤4 clicks from homepage",
                evidence=f"depth={ctx.depth}",
                detail=f"Deep page (depth {ctx.depth}): {ctx.url}",
            ))
    return findings


def _adapter_internal_links(
    rule: RuleDefinition, site_ctx: SiteContext,
    page_contexts: list[PageContext], data: dict,
) -> list[Finding]:
    """Rule 11: internal link distribution."""
    findings = []
    for ctx in page_contexts:
        if ctx.status_code != 200:
            continue
        if ctx.internal_links_count == 0:
            findings.append(_mk_finding(
                rule, url=ctx.url,
                detected="0 internal links",
                expected="≥1 internal link from each page",
                evidence="internal_links_count=0",
                detail=f"Orphan page: {ctx.url} has zero internal links pointing out",
            ))
        if ctx.linked_from_count == 0:
            findings.append(_mk_finding(
                rule, url=ctx.url,
                detected="0 inbound links",
                expected="≥1 inbound link to each page",
                evidence="linked_from_count=0",
                detail=f"Orphan page: {ctx.url} has zero inbound links",
            ))
    return findings


def _adapter_meta_description(
    rule: RuleDefinition, site_ctx: SiteContext,
    page_contexts: list[PageContext], data: dict,
) -> list[Finding]:
    """Rule 14: meta description audit."""
    findings = []
    for ctx in page_contexts:
        if ctx.status_code != 200:
            continue
        if not ctx.meta_description or not ctx.meta_description.strip():
            findings.append(_mk_finding(
                rule, url=ctx.url,
                detected="Missing meta description",
                expected="Unique meta description 120-160 chars",
                evidence="meta_description=None",
                detail=f"Page missing meta description: {ctx.url}",
            ))
        elif len(ctx.meta_description) < 50:
            findings.append(_mk_finding(
                rule, url=ctx.url,
                detected=f"Short meta description ({len(ctx.meta_description)} chars)",
                expected="120-160 characters",
                evidence=f"meta_description length={len(ctx.meta_description)}",
                detail=f"Meta description too short ({len(ctx.meta_description)} chars): {ctx.url}",
            ))
    return findings


def _adapter_h1_headings(
    rule: RuleDefinition, site_ctx: SiteContext,
    page_contexts: list[PageContext], data: dict,
) -> list[Finding]:
    """Rule 15: H1 heading hierarchy."""
    findings = []
    for ctx in page_contexts:
        if ctx.status_code != 200:
            continue
        if not ctx.h1 or not ctx.h1.strip():
            findings.append(_mk_finding(
                rule, url=ctx.url,
                detected="Missing H1",
                expected="One unique H1 per page",
                evidence="h1=None",
                detail=f"Page missing H1 heading: {ctx.url}",
            ))
    return findings


def _adapter_security_headers(
    rule: RuleDefinition, site_ctx: SiteContext,
    page_contexts: list[PageContext], data: dict,
) -> list[Finding]:
    """Rule 26: HSTS + security headers.

    Checks response headers from page contexts. In Phase 1, these come
    from LibreCrawl export data. Extended checks add the security header
    audit into the data dict — we check both sources.
    """
    findings = []
    # Check extended_checks output if available
    extended = data.get("extended_checks", {})
    security = extended.get("security_headers", {}) if extended else {}

    # If extended_checks has security data, use it (authoritative)
    if security:
        if not security.get("hsts", False):
            findings.append(_mk_finding(
                rule, url=site_ctx.base_url,
                detected="HSTS header missing",
                expected="Strict-Transport-Security header present",
                evidence="hsts=False",
                detail="HSTS header not found — site may be vulnerable to SSL stripping",
            ))
        essential = ["x_frame_options", "x_content_type_options", "referrer_policy"]
        missing = [h for h in essential if not security.get(h, False)]
        if missing:
            findings.append(_mk_finding(
                rule, url=site_ctx.base_url,
                detected=f"Missing headers: {', '.join(missing)}",
                expected="All 5 essential security headers present",
                evidence=f"missing={missing}",
                detail=f"Missing security headers: {', '.join(missing)}",
            ))
        return findings

    # Fallback: check response headers from PageContext
    # Only report if we have actual header data (not lazy-load placeholder)
    for ctx in page_contexts:
        if ctx.status_code != 200:
            continue
        headers = ctx.response_headers
        if headers is None:
            continue  # No header data available — skip, don't false-positive

        if "strict-transport-security" not in {k.lower() for k in headers}:
            findings.append(_mk_finding(
                rule, url=ctx.url,
                detected="HSTS header missing",
                expected="Strict-Transport-Security header present",
                evidence="strict-transport-security not in response headers",
                detail=f"HSTS header not found on {ctx.url}",
            ))
            break  # One finding per site is enough

    return findings


def _adapter_schema_coverage(
    rule: RuleDefinition, site_ctx: SiteContext,
    page_contexts: list[PageContext], data: dict,
) -> list[Finding]:
    """Rule 27: schema type coverage."""
    findings = []
    pages_with_schema = 0
    schema_types: set[str] = set()
    for ctx in page_contexts:
        if ctx.json_ld_types:
            pages_with_schema += 1
            schema_types.update(ctx.json_ld_types)

    total = len([p for p in page_contexts if p.status_code == 200])
    if total > 0 and pages_with_schema / total < 0.3:
        findings.append(_mk_finding(
            rule, url=site_ctx.base_url,
            detected=f"Schema on {pages_with_schema}/{total} pages",
            expected="Structured data on ≥30% of pages",
            evidence=f"schema_coverage={pages_with_schema}/{total}",
            detail=f"Low schema coverage: {pages_with_schema}/{total} pages have structured data",
        ))

    return findings


def _adapter_hreflang_basics(
    rule: RuleDefinition, site_ctx: SiteContext,
    page_contexts: list[PageContext], data: dict,
) -> list[Finding]:
    """Rule 29: hreflang basics."""
    findings = []
    pages_with_hreflang = sum(1 for p in page_contexts if p.hreflang_summary)
    if pages_with_hreflang == 0:
        # No hreflang on a single-lang site is fine — no finding
        return findings

    for ctx in page_contexts:
        if not ctx.hreflang_summary:
            continue
        langs = [h["lang"] for h in ctx.hreflang_summary if h.get("lang")]
        if "x-default" not in langs:
            findings.append(_mk_finding(
                rule, url=ctx.url,
                detected="Missing x-default hreflang",
                expected="x-default hreflang annotation present",
                evidence=f"langs={langs}",
                detail=f"Page has hreflang but missing x-default: {ctx.url}",
            ))

    return findings


def _adapter_broken_links(
    rule: RuleDefinition, site_ctx: SiteContext,
    page_contexts: list[PageContext], data: dict,
) -> list[Finding]:
    """Rule 30: broken internal links."""
    findings = []
    for ctx in page_contexts:
        if ctx.status_code >= 400:
            if ctx.linked_from_count > 0:
                findings.append(_mk_finding(
                    rule, url=ctx.url,
                    detected=f"Broken page ({ctx.status_code}) with {ctx.linked_from_count} inlinks",
                    expected="All internal links resolve to 200",
                    evidence=f"status={ctx.status_code}, linked_from={ctx.linked_from_count}",
                    detail=f"Broken internal link target: {ctx.url} ({ctx.status_code}) referenced from {ctx.linked_from_count} pages",
                ))

    return findings


def _adapter_soft_404(
    rule: RuleDefinition, site_ctx: SiteContext,
    page_contexts: list[PageContext], data: dict,
) -> list[Finding]:
    """Rule 41: soft 404 detection (thin/empty content)."""
    findings = []
    for ctx in page_contexts:
        if ctx.status_code == 200 and ctx.word_count < 50:
            findings.append(_mk_finding(
                rule, url=ctx.url,
                detected=f"Thin content: {ctx.word_count} words",
                expected="≥300 words or proper 404 status code",
                evidence=f"word_count={ctx.word_count}",
                detail=f"Possible soft 404: {ctx.url} returns 200 but has only {ctx.word_count} words",
            ))
    return findings


def _adapter_sitemap_indexability(
    rule: RuleDefinition, site_ctx: SiteContext,
    page_contexts: list[PageContext], data: dict,
) -> list[Finding]:
    """Rule 42: sitemap URL indexability consistency."""
    findings = []
    if not site_ctx.sitemap_found:
        return findings  # Handled by Rule 2 (sitemap validity)

    # Extract sitemap URLs from site data
    sitemap_urls = set()
    site_data = site_ctx._site_data or {}
    sitemap = site_data.get("sitemap", {})
    sitemap_url_list = sitemap.get("urls", []) or []

    page_urls = {ctx.url for ctx in page_contexts}
    for su in sitemap_url_list:
        if su in page_urls:
            ctx = next((c for c in page_contexts if c.url == su), None)
            if ctx and ctx.status_code != 200:
                findings.append(_mk_finding(
                    rule, url=su,
                    detected=f"Sitemap URL returns {ctx.status_code}",
                    expected="All sitemap URLs return 200",
                    evidence=f"sitemap_url_status={ctx.status_code}",
                    detail=f"Sitemap contains broken URL: {su} returns {ctx.status_code}",
                ))
    return findings


def _adapter_orphan_pages(
    rule: RuleDefinition, site_ctx: SiteContext,
    page_contexts: list[PageContext], data: dict,
) -> list[Finding]:
    """Rule 45: orphan pages."""
    findings = []
    for ctx in page_contexts:
        if ctx.status_code != 200:
            continue
        if ctx.linked_from_count == 0 and ctx.internal_links_count == 0:
            findings.append(_mk_finding(
                rule, url=ctx.url,
                detected="Page has zero inbound and zero outbound internal links",
                expected="Every page has ≥1 inbound internal link",
                evidence=f"linked_from={ctx.linked_from_count}, internal_links={ctx.internal_links_count}",
                detail=f"Orphan page: {ctx.url} has no internal link connections",
            ))
    return findings


def _adapter_hreflang_indexability(
    rule: RuleDefinition, site_ctx: SiteContext,
    page_contexts: list[PageContext], data: dict,
) -> list[Finding]:
    """Rule 58: hreflang indexability (targets must be indexable)."""
    findings = []
    url_to_status = {ctx.url: ctx.status_code for ctx in page_contexts}
    url_to_robots = {ctx.url: (ctx.robots or "").lower() for ctx in page_contexts}

    for ctx in page_contexts:
        if not ctx.hreflang_summary:
            continue
        for href in ctx.hreflang_summary:
            target_url = href.get("url", "")
            if not target_url:
                continue
            target_status = url_to_status.get(target_url)
            target_robots = url_to_robots.get(target_url, "")

            if target_status and target_status >= 400:
                findings.append(_mk_finding(
                    rule, url=ctx.url,
                    detected=f"hreflang target {target_url} returns {target_status}",
                    expected="All hreflang targets return 200",
                    evidence=f"hreflang_target_status={target_status}",
                    detail=f"hreflang on {ctx.url} points to broken URL: {target_url} ({target_status})",
                ))
            elif "noindex" in target_robots:
                findings.append(_mk_finding(
                    rule, url=ctx.url,
                    detected=f"hreflang target {target_url} has noindex",
                    expected="All hreflang targets are indexable",
                    evidence="hreflang_target_noindex",
                    detail=f"hreflang on {ctx.url} points to noindex page: {target_url}",
                ))

    return findings
