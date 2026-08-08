# Phase 2 — EXISTING_PARTIAL Rule Enhancement Scope

**Date:** 2026-08-09
**Baseline:** `21f6a0c` (`feat/master-audit-foundation`)
**Target:** 24 EXISTING_PARTIAL rules — local-only enhancement, no external APIs

---

## Classification: Before Phase 2

```
EXISTING_FULL:     18
EXISTING_PARTIAL:  24  ← Phase 2 target
NEW_AUTO:           9
NEW_EXTERNAL_DATA: 16
NEW_MANUAL:        13
────────────────────
TOTAL:             80
```

---

## Data Availability Assessment

LibreCrawl `EXPORT_FIELDS` (server.py:103-120) currently exports:

```
url, status_code, title, meta_description, h1, h2, h3,
word_count, canonical_url, depth, issues_detected, response_time_ms,
links_detailed, internal_links, external_links, linked_from,
images, broken_images,
robots, lang, charset, viewport, size, redirects, error_type,
og_tags, twitter_tags, json_ld, hreflang, analytics
```

**NOT in EXPORT_FIELDS**: `response_headers`, `body_html`, `body_text`

This means:
- HTML body content is **NOT** available for breadcrumb detection, thin content analysis, near-duplicate detection, form analysis, or schema-vs-visible comparison
- Response headers are **NOT** available for cache/CDN audits (Rules 23, 66)

**Phase 2 constraint**: Cannot modify EXPORT_FIELDS (would require crawl infrastructure change). Must work with what's available.

---

## Bucket A — LOCAL_IMPLEMENTABLE (14 rules)

Sufficient data from existing crawl export to add substantive detection.

### A.1 — Rule 10: Breadcrumb

| Field | Value |
|-------|-------|
| **Data available** | `json_ld` (BreadcrumbList schema already validated), `url` path segments |
| **New capability** | Breadcrumb consistency: compare schema breadcrumb with URL path hierarchy |
| **Cannot do** | Visual DOM breadcrumb detection (no `body_html` in export) |
| **Output** | Schema breadcrumb presence, item count, path-segment consistency |
| **Post-Phase 2** | Likely remains EXISTING_PARTIAL (visual detection blocked) |

### A.2 — Rule 12: Pagination / Faceted Navigation

| Field | Value |
|-------|-------|
| **Data available** | `url`, `canonical_url`, `robots`, `status_code`, `links_detailed` |
| **New capability** | Pagination URL pattern detection, self-canonical verification, parameter explosion detection, faceted URL pattern identification |
| **Cannot do** | DOM-based pagination markup detection (rel=next/prev remain INFO) |
| **Output** | pagination_pages_detected, faceted_urls_detected, canonical_issues, indexability_issues |

### A.3 — Rule 16: Thin Content

| Field | Value |
|-------|-------|
| **Data available** | `word_count`, `title`, `meta_description`, `h1`, `url`, `canonical_url`, `status_code` |
| **New capability** | Compound thin-content scoring: word_count + boilerplate indicators + template similarity + page type heuristics |
| **Cannot do** | Full text unique-content ratio (no body_text) |
| **Detection** | Low word_count AND short/missing meta AND short/missing h1 AND template-like structure → elevated risk. Category/contact/privacy pages NOT auto-flagged |
| **Output** | word_count, short_title, short_meta, short_h1, template_likelihood, risk_score |

### A.4 — Rule 17: Near-Duplicate Content

| Field | Value |
|-------|-------|
| **Data available** | `title`, `meta_description`, `h1`, `og_tags`, `twitter_tags`, `canonical_url`, `url` |
| **New capability** | Title/meta/H1 near-duplicate detection using fuzzy matching (Levenshtein/similarity ratio); og:title duplication check |
| **Cannot do** | Full body-text near-duplicate (no body_text) |
| **Performance** | O(n) per check using existing title/h1/meta fields; no O(n²) full-body comparison |
| **Threshold** | Configurable SIMILARITY_THRESHOLD (default 0.85) |
| **Output** | source_url, duplicate_url, similarity, matched_field, evidence |

### A.5 — Rule 28: Schema Conflict

| Field | Value |
|-------|-------|
| **Data available** | `json_ld` (full JSON-LD blocks including @type, @id, all properties) |
| **New capability** | Multi-block conflict detection: duplicate @type with conflicting properties (name, url, logo, sameAs for Organization; name, sku, brand for Product) |
| **Cannot do** | Non-JSON-LD schema (microdata/RDFa — not in crawl export) |
| **Detection** | Identity conflict (same @type, different @id, conflicting key properties) — not entity count |
| **Output** | conflicting_blocks, property, value_a, value_b, conflict_type |

### A.6 — Rule 37: WordPress SEO Plugin Conflict

| Field | Value |
|-------|-------|
| **Data available** | `og_tags`, `twitter_tags`, `json_ld`, `meta_description`, `robots`, `canonical_url` |
| **New capability** | Fingerprint detection: known generator patterns in meta/OG/schema output; duplicate OG/Twitter detection; multiple schema generators |
| **Cannot do** | Plugin list from WP Admin; definitive single-plugin confirmation |
| **Detection** | Fingerprint matching (Yoast, Rank Math, AIOSEO markers) → WARNING with confidence; output conflicts → FAIL |
| **Output** | detected_fingerprints, conflicting_outputs, confidence |

### A.7 — Rule 38: Permalink

| Field | Value |
|-------|-------|
| **Data available** | `url` for all crawled pages |
| **New capability** | Pattern detection: `?p=123`, `index.php` in URL, mixed post-type patterns, trailing-slash inconsistency, case-equivalent duplicates |
| **Cannot do** | Rewrite rule verification (server-side) |
| **Detection** | Structural permalink issues only; `.html`/`.htm` NOT flagged as issues; long URLs NOT auto-flagged |
| **Output** | url_pattern, issue_type, affected_urls, recommendation |

### A.8 — Rule 40: Audit Deliverables (master-audit-tasks.csv)

| Field | Value |
|-------|-------|
| **Data available** | All findings from V3 pipeline, registry metadata |
| **New capability** | Generate `{domain}-{timestamp}.master-audit-tasks.csv` — finding-level actionable task list sorted by priority |
| **Columns** | audit_id, rule_id, category, priority, url, finding, evidence, seo_impact, remediation, owner, acceptance_criteria, status |
| **Sort** | Critical → High → Medium → Low; within same priority: by finding_count / business impact |
| **Format** | Generic CSV (importable to Jira/Trello/Excel later) |

### A.9 — Rule 49: URL Normalization

| Field | Value |
|-------|-------|
| **Data available** | `url` for all crawled pages |
| **New capability** | Detect: uppercase path, duplicate slashes, spaces, non-ASCII chars, underscores, index.html/php variants, trailing-slash inconsistency, case-equivalent duplicates |
| **Severity** | non-ASCII/underscore → Opportunity/Info only; same-content-multiple-URLs → High/Critical |
| **Output** | url, issue_type, normalized_form, severity |

### A.10 — Rule 50: Redirect Relevance

| Field | Value |
|-------|-------|
| **Data available** | `url`, `status_code`, `redirects`, `links_detailed`, `linked_from` |
| **New capability** | Heuristic: bulk-to-homepage detection, unrelated-source-same-target, cross-language redirect, path-token similarity |
| **Cannot do** | Semantic content relevance (no body_text) |
| **Confidence** | HIGH/MEDIUM/LOW; LOW confidence → Opportunity/Manual Review only |
| **Output** | source_url, target_url, redirect_type, similarity_score, confidence |

### A.11 — Rule 59: Language / Hreflang Content Match

| Field | Value |
|-------|-------|
| **Data available** | `hreflang`, `lang` (HTML lang attribute), `title` |
| **New capability** | Compare declared hreflang code vs html lang attribute; detect mismatches |
| **Cannot do** | Body text language detection (no body_text); cannot detect ML translation quality |
| **Minimum text** | Require sufficient text indicators (title + meta available); UNKNOWN if insufficient |
| **Output** | declared_lang, hreflang_lang, mismatch, confidence |

### A.12 — Rule 70: Form Accessibility

| Field | Value |
|-------|-------|
| **Data available** | None directly — form HTML not in export fields |
| **New capability** | **BLOCKED**: No form HTML in EXPORT_FIELDS |
| **Phase 2 action** | Document gap; implement placeholder check using known UI patterns |
| **Coverage** | EXECUTED_PARTIAL — notes that form detection requires rendered DOM |

**Reassessment**: Rule 70 cannot be meaningfully implemented without `body_html`. Move to Bucket C for Phase 2? Or implement what's possible?

The spec says to try. We can check if any pages reference form-related URLs (e.g., `/contact`, `/login`, `/search`) and note that forms should be checked. But without HTML, actual form accessibility checks are impossible. → Minimal implementation; remains EXISTING_PARTIAL.

### A.13 — Rule 78: Schema vs Visible Content

| Field | Value |
|-------|-------|
| **Data available** | `json_ld` (schema properties), `title`, `meta_description`, `og_tags` |
| **New capability** | Compare schema values against visible metadata (title, meta, OG tags); check for consistency |
| **Cannot do** | Full body-text comparison (no body_text); cannot compare schema vs visible body content |
| **Detection** | Product name/Organization name in json_ld vs og:title/title; price/availability in schema vs OG product tags where present |
| **Output** | schema_value, visible_value, match_type, confidence |

### A.14 — Rule 79: Image ALT / Link Quality

| Field | Value |
|-------|-------|
| **Data available** | `images` (alt, src, broken, status), `links_detailed` |
| **New capability** | Beyond missing-alt: very short meaningless alt, very long alt, filename-only alt, repeated identical alt across unrelated images, possible keyword stuffing, linked images with empty accessible name |
| **Cannot do** | Image content analysis (no visual data) |
| **Heuristic** | alt >125 chars → WARNING (not FAIL); alt="" on decorative images → intentionally allowed |
| **Output** | image_url, alt_text, issue_type, evidence |

---

## Bucket B — CONDITIONAL_LOCAL (2 rules)

### B.1 — Rule 23: Cache / CDN

| Field | Value |
|-------|-------|
| **Required data** | `response_headers` with cache-control, age, cf-cache-status, x-cache, server, via, cdn-loop |
| **Available in EXPORT_FIELDS?** | **NO** — `response_headers` not exported |
| **Phase 2 status** | **BLOCKED** — cannot implement without headers |
| **Action** | Document gap; keep EXISTING_PARTIAL |
| **Coverage** | NOT_CHECKED with reason: "response_headers unavailable in crawl export" |

### B.2 — Rule 66: WP Cache/CDN Synergy

| Field | Value |
|-------|-------|
| **Required data** | `response_headers` with x-litespeed-cache, x-cache-status, wp-super-cache, w3-total-cache markers |
| **Available in EXPORT_FIELDS?** | **NO** — `response_headers` not exported |
| **Phase 2 status** | **BLOCKED** — cannot implement without headers |
| **Action** | Document gap; keep EXISTING_PARTIAL |
| **Coverage** | NOT_CHECKED with reason: "response_headers unavailable in crawl export" |

---

## Bucket C — EXTERNAL_BLOCKED (8 rules)

These rules require external APIs, server access, or data not in crawl export. No Phase 2 implementation.

| ID | Rule | Blocked By | Data Source Needed |
|:--:|------|-----------|-------------------|
| 2 | XML Sitemap submission status | GSC API | GSC |
| 5 | Crawl Budget | GSC + Server Logs | GSC, Server Logs |
| 13 | Title CTR / search intent | GSC + Semrush | GSC, Semrush |
| 19 | Core Web Vitals (LCP/CLS/INP) | PageSpeed API | PageSpeed API |
| 20 | TTFB / geo / cache state | Server Logs | LibreCrawl + Server Logs |
| 22 | PSI image opportunities | PageSpeed API | LibreCrawl + PageSpeed API |
| 25 | HTTPS certificate chain / expiry | External SSL check | LibreCrawl |
| 61 | Field vs Lab data | PageSpeed API | PageSpeed API |

---

## Summary

| Bucket | Count | Rules | Phase 2 Action |
|--------|:-----:|-------|---------------|
| **A — LOCAL_IMPLEMENTABLE** | **14** | 10, 12, 16, 17, 28, 37, 38, 40, 49, 50, 59, 70, 78, 79 | Implement with existing data; partial implementation accepted where data limited |
| **B — CONDITIONAL (BLOCKED)** | **2** | 23, 66 | Inspected → blocked (no response_headers in export); remain PARTIAL |
| **C — EXTERNAL_BLOCKED** | **8** | 2, 5, 13, 19, 20, 22, 25, 61 | No Phase 2 action; remain EXISTING_PARTIAL |

**Realistic promotion target**: 0–14 rules. Depends on acceptance criteria satisfaction.

---

## Implementation Order

1. **Rule 40** — task CSV artifact (new output, no check logic)
2. **Rule 38** — permalink detection (URL-only, low risk)
3. **Rule 49** — URL normalization (URL-only, low risk)
4. **Rule 17** — near-duplicate (metadata-based fuzzy match)
5. **Rule 28** — schema conflict (JSON-LD analysis)
6. **Rule 79** — image ALT quality (images data already present)
7. **Rule 16** — thin content (compound scoring)
8. **Rule 12** — pagination/faceted nav (URL pattern + canonical)
9. **Rule 10** — breadcrumb (schema + URL path consistency)
10. **Rule 37** — SEO plugin fingerprints (meta/OG/schema patterns)
11. **Rule 59** — language/hreflang match (hreflang vs lang attr)
12. **Rule 78** — schema vs metadata (json_ld vs OG/meta)
13. **Rule 50** — redirect relevance (heuristic with confidence)
14. **Rule 70** — form accessibility (minimal — note gap)

---

## Rules Remaining EXISTING_PARTIAL After Phase 2

| ID | Rule | Reason |
|:--:|------|--------|
| 2 | XML Sitemap | GSC API required |
| 5 | Crawl Budget | GSC + Server Logs required |
| 13 | Title CTR | GSC + Semrush required |
| 19 | Core Web Vitals | PageSpeed API required |
| 20 | TTFB | Server Logs required |
| 22 | PSI Images | PageSpeed API required |
| 23 | Cache/CDN | response_headers not in crawl export |
| 25 | Certificate | External SSL check required |
| 61 | Field vs Lab | PageSpeed API required |
| 66 | WP Cache | response_headers not in crawl export |
| + any Bucket A rule not meeting acceptance criteria | | |

---

## Implementation Constraints (Reconfirmed)

- ✅ No GSC, PageSpeed, Semrush, GA4 API calls
- ✅ No Server Logs, SSH, WP Admin access
- ✅ No new HTTP requests
- ✅ No EXPORT_FIELDS modification
- ✅ No legacy check modification
- ✅ Feature flag MASTER_AUDIT_V3_ENABLED gates all V3 output
- ✅ All new logic in `checks/` module
- ✅ TDD: fixture FAIL → implement → PASS → regression suite
