"""Phase 2 — Local Check Implementation for Form Accessibility Rules.

Rule 70: Form Accessibility (check_form_accessibility)

Pure functions using existing LibreCrawl export data only.
No HTTP requests, no external APIs.

CRITICAL LIMITATION:
  This module is intentionally minimal. The crawl export does NOT include
  body_html or rendered DOM, which means we cannot inspect:
    - <form> element structure
    - <input>, <label>, <select>, <textarea> elements
    - ARIA attributes (aria-label, aria-describedby, aria-required)
    - <fieldset> / <legend> groupings
    - Form submission method and action
    - Client-side validation attributes

  A real form accessibility audit requires rendered DOM or JS rendering,
  which is NOT available in Phase 2 of this audit system.

  This module therefore:
    1. Detects likely form pages via URL patterns and external platform links
    2. Produces COVERAGE GAP findings documenting what CANNOT be checked
    3. Lists URLs that should be manually reviewed
    4. Does NOT produce false findings from incomplete data
"""

from __future__ import annotations

import re
import logging
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
# Form-relevant URL patterns
# ---------------------------------------------------------------------------

# URL path patterns that suggest a page likely contains a form
_FORM_URL_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("contact_form", re.compile(r"/(contact|contact-us|get-in-touch)(/|\.|$)", re.IGNORECASE)),
    ("login", re.compile(r"/(login|signin|sign-in|log-in|auth)(/|\.|$)", re.IGNORECASE)),
    ("signup", re.compile(r"/(signup|sign-up|register|registration|create-account|join)(/|\.|$)", re.IGNORECASE)),
    ("search", re.compile(r"/(search|buscar|busca|suche|recherche)(/|\.|$)", re.IGNORECASE)),
    ("checkout", re.compile(r"/(checkout|cart|basket|order|pay|payment)(/|\.|$)", re.IGNORECASE)),
    ("newsletter", re.compile(r"/(newsletter|subscribe|mailing-list)(/|\.|$)", re.IGNORECASE)),
    ("feedback", re.compile(r"/(feedback|survey|review|rate)(/|\.|$)", re.IGNORECASE)),
    ("support", re.compile(r"/(support|help|ticket)(/|\.|$)", re.IGNORECASE)),
    ("booking", re.compile(r"/(book|booking|reservation|reserve|schedule|appointment)(/|\.|$)", re.IGNORECASE)),
    ("application", re.compile(r"/(apply|application|job|career|hiring)(/|\.|$)", re.IGNORECASE)),
    ("quote", re.compile(r"/(quote|estimate|quotation|rfq)(/|\.|$)", re.IGNORECASE)),
    ("donation", re.compile(r"/(donate|donation|giving|contribute)(/|\.|$)", re.IGNORECASE)),
    ("comment", re.compile(r"/(comment|reply|discuss|forum)(/|\.|$)", re.IGNORECASE)),
    ("profile", re.compile(r"/(profile|account|settings|preferences)(/|\.|$)", re.IGNORECASE)),
    ("password_reset", re.compile(r"/(forgot|reset|password|recover)(/|\.|$)", re.IGNORECASE)),
]

# Known third-party form platforms (detected via external links)
_FORM_PLATFORM_DOMAINS: set[str] = {
    "typeform.com",
    "jotform.com",
    "forms.gle",
    "formstack.com",
    "wufoo.com",
    "formspree.io",
    "paperform.co",
    "cognitoforms.com",
    "formkeep.com",
    "formcarry.com",
    "getform.io",
    "basin.com",
    "formspark.io",
    "surveygizmo.com",
    "surveymonkey.com",
    "qualtrics.com",
    "hubspot.com",         # HubSpot forms
    "pardot.com",          # Pardot forms (Salesforce)
    "marketo.com",         # Marketo forms
    "mailchimp.com",       # Mailchimp embedded forms
    "convertkit.com",      # ConvertKit forms
    "activecampaign.com",  # ActiveCampaign forms
}


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def _detect_form_url_pattern(url: str) -> Optional[str]:
    """Check if URL path matches known form-related patterns.

    Args:
        url: The page URL to check.

    Returns:
        The matched pattern name (e.g., "contact_form"), or None.
    """
    if not url:
        return None
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    path = parsed.path or ""
    for pattern_name, pattern in _FORM_URL_PATTERNS:
        if pattern.search(path):
            return pattern_name
    return None


def _detect_form_platform_links(links_detailed: list[dict]) -> list[str]:
    """Check if page links to known third-party form platforms.

    Args:
        links_detailed: List of link dicts from PageContext.

    Returns:
        List of matching form platform domain names found.
    """
    found: list[str] = []
    for link in links_detailed or []:
        link_url = link.get("url", "") or link.get("href", "")
        if not link_url:
            continue
        try:
            parsed = urlparse(link_url)
            hostname = (parsed.hostname or "").lower()
            # Check for exact domain or subdomain match
            for platform_domain in _FORM_PLATFORM_DOMAINS:
                if hostname == platform_domain or hostname.endswith("." + platform_domain):
                    if platform_domain not in found:
                        found.append(platform_domain)
        except Exception:
            continue
    return found


# ---------------------------------------------------------------------------
# Rule 70 — Form Accessibility
# ---------------------------------------------------------------------------

def check_form_accessibility(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 70: Form Accessibility.

    INTENTIONALLY MINIMAL — no body_html/rendered DOM in Phase 2 crawl export.

    Produces:
      1. One site-level INFO finding documenting the coverage gap and listing
         likely form URLs that need manual review.
      2. Per-page INFO findings for pages with form platform links (so the
         external form dependency is documented).

    The real form accessibility audit requires:
      - Rendered DOM (body_html) to inspect <form>, <input>, <label> elements
      - JS rendering for SPAs and dynamic forms
      - Accessibility tree inspection for ARIA attributes
    These are NOT available in Phase 2.

    Args:
        rule: RuleDefinition for this check.
        site_ctx: Site-level context.
        page_contexts: All page contexts from the crawl.
        data: Additional data dict (unused here).

    Returns:
        List of Finding objects (primarily INFO-level coverage gap documentation).
    """
    findings: list[Finding] = []

    # ---- Collect likely form pages ----
    likely_form_pages: list[dict] = []       # {url, indicator}
    pages_with_form_platforms: list[dict] = []  # {url, platforms}

    for ctx in page_contexts:
        if ctx.status_code != 200:
            continue

        url = ctx.url
        links_detailed = ctx.links_detailed or []

        url_pattern = _detect_form_url_pattern(url)
        platform_links = _detect_form_platform_links(links_detailed)

        if url_pattern:
            likely_form_pages.append({
                "url": url,
                "indicator": f"URL pattern matches '{url_pattern}'",
            })

        if platform_links:
            pages_with_form_platforms.append({
                "url": url,
                "platforms": platform_links,
            })
            # Also treat as likely form page if not already captured
            if not url_pattern:
                likely_form_pages.append({
                    "url": url,
                    "indicator": f"External links to form platforms: {', '.join(platform_links)}",
                })

    # ---- Site-level coverage gap finding ----
    if likely_form_pages:
        form_urls = [p["url"] for p in likely_form_pages]
        form_urls_preview = form_urls[:20]
        truncation_note = (
            f" (showing first 20 of {len(form_urls)}; remaining URLs logged)"
            if len(form_urls) > 20 else ""
        )

        findings.append(_mk(
            rule=rule,
            url="SITE",
            detected=(
                f"Phase 2 form accessibility check is LIMITED — "
                f"no DOM/form HTML available in crawl export. "
                f"{len(form_urls)} likely form page(s) identified by URL patterns"
                f"{truncation_note}."
            ),
            expected=(
                "All forms should have: associated <label> elements, "
                "proper <fieldset>/<legend> groupings, ARIA attributes where needed, "
                "clear error messages, keyboard navigability, and accessible "
                "submit buttons"
            ),
            evidence=(
                f"likely_form_urls={form_urls_preview}, "
                f"total_likely_forms={len(form_urls)}"
            ),
            detail=(
                f"Form accessibility cannot be fully checked in Phase 2 because "
                f"the crawl export does not include body_html or rendered DOM. "
                f"Without the DOM, we cannot inspect <form>, <input>, <label>, "
                f"<select>, <textarea>, ARIA attributes, fieldset/legend groupings, "
                f"or form submission mechanisms. "
                f"Manual review is required for the following {len(form_urls)} "
                f"likely form page(s){truncation_note}: "
                f"{', '.join(form_urls_preview)}. "
                f"A full form audit requires rendered DOM access (Phase 3+)."
            ),
            severity=Severity.INFO,
            confidence=1.0,
        ))

        # Log the full list for audit records
        if len(form_urls) > 20:
            logger.info(
                "check_form_accessibility: Full likely form URLs (%d total): %s",
                len(form_urls), form_urls,
            )

    else:
        # No form pages detected — still document the coverage gap
        findings.append(_mk(
            rule=rule,
            url="SITE",
            detected=(
                "Phase 2 form accessibility check is LIMITED — "
                "no DOM/form HTML available in crawl export. "
                "No form pages identified by URL patterns."
            ),
            expected=(
                "All forms should be accessible and properly labeled"
            ),
            evidence="No likely form URLs detected by URL pattern matching",
            detail=(
                f"Form accessibility cannot be verified in Phase 2 because "
                f"the crawl export does not include body_html or rendered DOM. "
                f"No likely form pages were identified by URL pattern matching, "
                f"but forms may still exist on the site (e.g., in-page contact "
                f"forms on non-obvious URLs, modal forms, or dynamically loaded forms). "
                f"A full form audit requires rendered DOM access (Phase 3+)."
            ),
            severity=Severity.INFO,
            confidence=1.0,
        ))

    # ---- Per-page findings for external form platforms ----
    for page_info in pages_with_form_platforms[:30]:  # Cap to avoid excessive output
        page_url = page_info["url"]
        platforms = page_info["platforms"]

        findings.append(_mk(
            rule=rule,
            url=page_url,
            detected=f"External form platform(s) detected: {', '.join(platforms)}",
            expected=(
                "Third-party forms should be embedded accessibly and "
                "conform to WCAG 2.1 AA standards"
            ),
            evidence=f"page={page_url}, platforms={platforms}",
            detail=(
                f"Page {page_url} links to or embeds third-party form "
                f"platform(s): {', '.join(platforms)}. "
                f"Third-party forms must be verified for accessibility "
                f"(keyboard navigation, screen reader compatibility, "
                f"WCAG 2.1 AA compliance). Many embedded form widgets "
                f"have known a11y issues. Manual testing with assistive "
                f"technology is recommended."
            ),
            severity=Severity.INFO,
            confidence=0.9,
        ))

    if len(pages_with_form_platforms) > 30:
        logger.info(
            "check_form_accessibility: Capped external form platform findings "
            "at 30 (total %d pages with form platforms)",
            len(pages_with_form_platforms),
        )

    return findings
