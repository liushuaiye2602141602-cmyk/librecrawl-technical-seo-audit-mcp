"""Phase 2 — Local Check Implementation for International / Multilingual Rules.

Rule 59: Language / Hreflang Content Match (check_language_hreflang_match)

Pure functions using existing LibreCrawl export data only.
No HTTP requests, no external APIs.

Limitation (documented): Body-text based language detection is NOT available
in Phase 2 because the crawl export does not include body_text. This module
validates declared language consistency (html lang vs hreflang), hreflang
self-reference, and hreflang entry integrity.
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
# Constants
# ---------------------------------------------------------------------------

# Default minimum word count for language analysis
_DEFAULT_MIN_TEXT_THRESHOLD = 50

# Valid language code pattern: xx or xx-YY (e.g., "en", "en-US", "zh-Hans", "es-419")
# ISO 639-1 (2 letters), optional ISO 3166-1 alpha-2 region (2 letters) or ISO 15924 script (4 letters)
# or UN M.49 numeric region (3 digits)
_VALID_LANG_RE = re.compile(
    r"^[a-z]{2,3}(-[A-Z][a-z]{3})?(-[A-Z]{2})?$|"
    r"^[a-z]{2,3}(-[A-Z][a-z]{3})?(-[0-9]{3})?$"
)

# Simpler practical check: common patterns seen in the wild
_PRACTICAL_LANG_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?$")


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _validate_lang_code(code: str) -> bool:
    """Validate that a language/region code looks plausible.

    Accepts patterns like: 'en', 'en-US', 'zh-Hans', 'es-419', 'fr-CA'.

    Returns:
        True if the code matches common hreflang patterns.
    """
    if not code or not code.strip():
        return False
    code = code.strip()
    if code.lower() == "x-default":
        return True
    return bool(_PRACTICAL_LANG_RE.match(code))


def _normalize_lang_code(code: str) -> str:
    """Normalize a lang code for comparison: lowercase lang, uppercase region.

    'EN-us' -> 'en-US'
    """
    code = code.strip()
    if "-" in code:
        parts = code.split("-", 1)
        lang = parts[0].lower()
        region = parts[1].upper() if len(parts[1]) <= 4 else parts[1]
        return f"{lang}-{region}"
    return code.lower()


def _find_self_referencing_hreflang(
    page_url: str,
    hreflang_entries: list[dict],
) -> Optional[dict]:
    """Find the hreflang entry that points back to this page's URL.

    Args:
        page_url: The URL of the current page.
        hreflang_entries: List of {lang, url} dicts from hreflang_summary.

    Returns:
        The matching hreflang entry dict, or None if no self-reference found.
    """
    page_url_norm = page_url.rstrip("/").lower()
    for entry in hreflang_entries:
        entry_url = (entry.get("url") or "").rstrip("/").lower()
        if entry_url and entry_url == page_url_norm:
            return entry
    return None


# ---------------------------------------------------------------------------
# Rule 59 — Language / Hreflang Content Match
# ---------------------------------------------------------------------------

def check_language_hreflang_match(
    rule: RuleDefinition,
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    data: dict,
) -> list[Finding]:
    """Rule 59: Language / Hreflang Content Match.

    Validates that declared HTML language and hreflang tags are consistent:
      1. html lang vs hreflang self-reference mismatch -> ERROR
      2. Missing self-referencing hreflang -> WARNING
      3. Duplicate lang codes with different URLs -> ERROR
      4. Invalid hreflang lang code format -> WARNING
      5. Body-text language detection NOT available -> INFO (coverage gap)

    Only checks pages with word_count >= MIN_TEXT_THRESHOLD that have
    hreflang tags.

    Args:
        rule: RuleDefinition for this check.
        site_ctx: Site-level context.
        page_contexts: All page contexts from the crawl.
        data: Additional data dict. May contain "lang_min_text" (int).

    Returns:
        List of Finding objects.
    """
    min_text_threshold = int(data.get("lang_min_text", _DEFAULT_MIN_TEXT_THRESHOLD))
    findings: list[Finding] = []

    pages_with_hreflang = 0
    pages_skipped_insufficient_text = 0
    pages_checked = 0

    for ctx in page_contexts:
        if ctx.status_code != 200:
            continue

        url = ctx.url

        # Get raw export data
        raw = ctx._raw_export or {}

        # Get declared HTML lang
        html_lang = (ctx.lang or raw.get("lang") or "").strip()

        # Get hreflang entries
        hreflang_entries: list[dict] = ctx.hreflang_summary or []
        # hreflang_entries is list of {"lang": str, "url": str}

        # Skip pages without any hreflang
        if not hreflang_entries:
            continue

        pages_with_hreflang += 1

        # Skip pages with insufficient text
        word_count = ctx.word_count or 0
        if word_count < min_text_threshold:
            pages_skipped_insufficient_text += 1
            continue

        pages_checked += 1

        # ---- Extract hreflang language codes with their URLs ----
        hreflang_by_lang: dict[str, list[str]] = {}
        invalid_lang_codes: list[str] = []

        for entry in hreflang_entries:
            lang_code = (entry.get("lang") or "").strip()
            entry_url = (entry.get("url") or "").strip()

            if not lang_code:
                continue

            # Check 4: Validate lang code format
            if not _validate_lang_code(lang_code):
                invalid_lang_codes.append(lang_code)

            normalized = _normalize_lang_code(lang_code)
            hreflang_by_lang.setdefault(normalized, []).append(entry_url)

        # ---- Check 4: Invalid lang code format ----
        for bad_code in invalid_lang_codes:
            findings.append(_mk(
                rule=rule,
                url=url,
                detected=f"Invalid hreflang language code: '{bad_code}'",
                expected="Valid language code format (e.g., 'en', 'en-US', 'zh-Hans')",
                evidence=f"page={url}, invalid_lang_code={bad_code}",
                detail=(
                    f"Page {url} has a hreflang entry with an invalid language code "
                    f"'{bad_code}'. Valid codes follow ISO 639-1 with optional "
                    f"ISO 3166-1 region (e.g., 'en', 'en-US', 'fr-CA'). "
                    f"Invalid codes are ignored by search engines, breaking hreflang "
                    f"implementation."
                ),
                severity=Severity.WARNING,
            ))

        # ---- Check 3: Duplicate lang codes with different URLs ----
        for lang_code, urls in hreflang_by_lang.items():
            unique_urls = list(dict.fromkeys(u.strip().lower() for u in urls if u.strip()))
            if len(unique_urls) > 1:
                findings.append(_mk(
                    rule=rule,
                    url=url,
                    detected=(
                        f"Hreflang code '{lang_code}' maps to {len(unique_urls)} "
                        f"different URLs: {', '.join(unique_urls)}"
                    ),
                    expected="Each language code should map to exactly one URL",
                    evidence=(
                        f"page={url}, "
                        f"lang_code={lang_code}, "
                        f"conflicting_urls={unique_urls}"
                    ),
                    detail=(
                        f"Page {url} has multiple hreflang entries with the same "
                        f"language code '{lang_code}' pointing to different URLs "
                        f"({', '.join(unique_urls)}). This creates ambiguity "
                        f"for search engines and can cause incorrect language/region "
                        f"targeting."
                    ),
                    severity=Severity.ERROR,
                ))

        # ---- Check 2: Missing self-referencing hreflang ----
        self_ref = _find_self_referencing_hreflang(url, hreflang_entries)
        if self_ref is None:
            findings.append(_mk(
                rule=rule,
                url=url,
                detected="Page has hreflang tags but no self-referencing entry",
                expected="Each hreflang group should include a self-referencing entry",
                evidence=(
                    f"page={url}, "
                    f"hreflang_langs={[e.get('lang', '') for e in hreflang_entries if e.get('lang')]}"
                ),
                detail=(
                    f"Page {url} uses hreflang annotations but does not include "
                    f"a self-referencing entry for its own URL. Best practice "
                    f"requires every page in a hreflang cluster to include a "
                    f"self-reference so search engines can validate the canonical "
                    f"language mapping."
                ),
                severity=Severity.WARNING,
            ))

        # ---- Check 1: html_lang vs hreflang self-reference mismatch ----
        if html_lang and self_ref is not None:
            hreflang_lang = (self_ref.get("lang") or "").strip()

            if hreflang_lang:
                html_norm = _normalize_lang_code(html_lang)
                hreflang_norm = _normalize_lang_code(hreflang_lang)

                if html_norm != hreflang_norm:
                    findings.append(_mk(
                        rule=rule,
                        url=url,
                        detected=(
                            f"HTML lang='{html_lang}' but self-referencing hreflang "
                            f"declares '{hreflang_lang}'"
                        ),
                        expected="HTML lang attribute should match self-referencing hreflang",
                        evidence=(
                            f"page={url}, "
                            f"html_lang={html_lang}, "
                            f"hreflang_self_lang={hreflang_lang}"
                        ),
                        detail=(
                            f"Page {url} declares html lang='{html_lang}' but the "
                            f"self-referencing hreflang tag specifies "
                            f"'{hreflang_lang}'. This inconsistency can confuse "
                            f"search engines about the page's intended language "
                            f"and lead to incorrect indexing or duplicate content "
                            f"issues in multilingual sites."
                        ),
                        severity=Severity.ERROR,
                    ))

    # ---- Coverage gap: body-text language detection not available ----
    if pages_with_hreflang > 0:
        logger.info(
            "check_language_hreflang_match: hreflang pages=%d, checked=%d, "
            "skipped (insufficient text)=%d, body-text language detection NOT available",
            pages_with_hreflang, pages_checked, pages_skipped_insufficient_text,
        )

    return findings
