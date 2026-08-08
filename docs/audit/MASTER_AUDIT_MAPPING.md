# Master Audit Mapping — 80 Items vs Existing Capabilities

> **Date**: 2026-08-09 | **Version**: Phase 1 Analysis

---

## Coverage Summary

| Classification | Count | % | Description |
|---|---|---|---|
| **EXISTING_FULL** | 18 | 22.5% | Rule fully implemented and matching 80-item spec |
| **EXISTING_PARTIAL** | 24 | 30.0% | Rule partially implemented; gaps identified below |
| **NEW_AUTO** | 9 | 11.25% | New rule that can be fully automated |
| **NEW_EXTERNAL_DATA** | 17 | 21.25% | Requires external data source (API key, platform access, server access) |
| **NEW_MANUAL** | 12 | 15.0% | Requires human review — cannot be fully automated |
| **TOTAL** | **80** | **100%** | — |

**Key metric**: After all phases complete, **68 of 80 rules (85%) can be at least partially automated**, up from ~55 fragmented checks today.

---

## Detailed Per-Rule Mapping

### Category: 抓取与索引 (Crawl & Index) — Rules 1–5, 41–45

| Rule | Status | Current Implementation | Gaps & Actions |
|------|--------|----------------------|----------------|
| 1. robots.txt | **EXISTING_FULL** | `_site_check()` fetches and validates `/robots.txt`; reports disallow count + sitemap declaration | None — complete. |
| 2. XML Sitemap | **EXISTING_PARTIAL** | `_site_check()` detects sitemap.xml presence and URL count; sitemap_recon.csv diffs crawled vs sitemap | **Gap**: No GSC/Bing submission status validation. **Action**: Add GSC sitemap status check to GSCDataProvider; keep core detection as-is. |
| 3. noindex/nofollow | **EXISTING_FULL** | `_build_report()` sections "Noindex" and "Analytics" check meta robots + X-Robots-Tag on every page | None — complete. |
| 4. 4xx/5xx Errors | **EXISTING_FULL** | Status code buckets with "Broken Pages" table including "Linked From" and anchor text | None — complete. |
| 5. Crawl Budget | **EXISTING_PARTIAL** | `extended_checks.py`: `spider_trap_calendar`, `url_session_id_high_entropy`, `faceted_url_explosion` — 3 trap types detected | **Gap**: No server log analysis, no GSC Crawl Stats integration. **Action**: Add ServerLogDataProvider for log-based crawl budget analysis; extend URL pattern detection for parameter/sort/filter traps. |
| 41. Soft 404 | **EXISTING_FULL** | `extended_checks.py`: `soft_404` — 200 + thin body + "not found" phrase fingerprint | None — complete. |
| 42. Sitemap Indexability | **EXISTING_FULL** | `extended_checks.py`: 6 sitemap cross-checks (noindex, 3xx, canonicalized, robots-disallowed, over_50k, over_50mb) | None — complete. |
| 43. Sitemap lastmod | **NEW_AUTO** | None | **Action**: Add `sitemap_lastmod_suspicious` check — detect: invalid format, future dates, all-URLs-same-date pattern, suspicious bulk refresh pattern, inconsistency when historical comparison data exists. Note: legitimate old pages may have old lastmod values — do NOT flag "older than X months" as Warning/Error. |
| 44. Google Canonical | **NEW_EXTERNAL_DATA** | None | **Requires**: GSC URL Inspection API. **Action**: Build GSCDataProvider enrichment that fetches Google-selected canonical for P0 pages and flags mismatches. |
| 45. Orphan Pages | **EXISTING_FULL** | `_build_report()` orphan detection via crawl link graph + sitemap cross-reference; sitemap_fill pages contribute inbound links since v1.6.2 | None — complete. |

### Category: URL 与重定向 (URL & Redirects) — Rules 6–8, 49–51

| Rule | Status | Current Implementation | Gaps & Actions |
|------|--------|----------------------|----------------|
| 6. Domain/Protocol | **EXISTING_FULL** | `_site_check()`: https_redirect + www_redirect behavior verified | None — complete. |
| 7. Redirect Chains | **EXISTING_FULL** | Full Source→Destination→Hops analysis with cycle detection in the MD report Redirects section | None — complete. |
| 8. Canonical | **EXISTING_FULL** | 6 canonical checks: missing, non-self, to_relative, to_redirect, chain_depth>1, outside_head | None — complete. |
| 49. URL Normalization | **EXISTING_PARTIAL** | 4 URL quality checks: spaces, multi-slash, non-ASCII, underscores | **Gap**: No case-sensitivity duplicate check, no trailing-slash consistency check, no index.* variant detection. **Action**: Expand URL quality rules to 8 checks covering the full normalization spectrum. |
| 50. Redirect Relevance | **EXISTING_PARTIAL** | Redirect chains listed with Source→Target | **Gap**: No semantic relevance check — cannot detect bulk-redirect-to-homepage or wrong-language redirects. **Action**: Add heuristic checks: flag redirects where target is homepage, where target language differs from source, where >N unrelated URLs redirect to same target. |
| 51. Internal Links→Redirects | **NEW_AUTO** | None | **Action**: Cross-reference `links` list against pages with 3xx status: flag every internal `<a href>` pointing to a redirect chain. Report the source pages and suggest updating to final destination. |

### Category: 站点架构 (Site Architecture) — Rules 9–12

| Rule | Status | Current Implementation | Gaps & Actions |
|------|--------|----------------------|----------------|
| 9. Click Depth | **EXISTING_FULL** | Deep pages (>4) flagged in report with depth distribution | None — complete. |
| 10. Breadcrumbs | **EXISTING_PARTIAL** | `schema_validator.py`: BreadcrumbList required fields validated | **Gap**: No visual breadcrumb detection in HTML. **Action**: Add HTML parsing for `.breadcrumb`, `[aria-label="breadcrumb"]`, `nav[aria-label="Breadcrumb"]` patterns; compare visual breadcrumb with schema BreadcrumbList. |
| 11. Internal Links | **EXISTING_FULL** | Orphan detection, inbound counts, nofollow patterns, anchor text analysis — complete coverage | None — complete. |
| 12. Faceted Navigation | **EXISTING_PARTIAL** | `faceted_url_explosion` detected | **Gap**: No pagination crawlability audit. **Action**: Check: (1) page URLs are crawlable, (2) real `<a href>` links used, (3) URLs unique, (4) no fragment-only navigation, (5) paginated pages return 200, (6) self-canonical where appropriate, (7) no accidental noindex, (8) internal links allow discovery of deeper pages, (9) faceted/sort URLs don't create uncontrolled crawl space. Note: `rel=next/prev` detection is INFO/OPTIONAL_COMPATIBILITY only — NOT a PASS/FAIL criterion. |

### Category: 内容与元数据 (Content & Metadata) — Rules 13–18, 52–56

| Rule | Status | Current Implementation | Gaps & Actions |
|------|--------|----------------------|----------------|
| 13. Title Uniqueness | **EXISTING_PARTIAL** | Missing/duplicate/long/short titles all detected | **Gap**: No search intent matching, no CTR analysis. **Action**: Preserve existing technical checks; intent matching remains NEW_MANUAL; CTR data from GSCDataProvider for identifying low-CTR titles. |
| 14. Meta Description | **EXISTING_FULL** | Missing/duplicate/long/short descriptions in Warnings section | None — complete. |
| 15. H1 & Heading Structure | **EXISTING_FULL** | H1 missing/duplicate/mismatch + full heading hierarchy tree | None — complete. |
| 16. Thin Content | **EXISTING_PARTIAL** | word_count < 300 flagged | **Gap**: No near-duplicate detection for thin content, no GSC engagement signals. **Action**: Extend content_audit's shingle analysis to flag pages with high boilerplate AND low word count as thin+duplicate; add GSC impression/CTR enrichment. |
| 17. Duplicate Content | **EXISTING_PARTIAL** | `content_audit.py`: 5-word shingle boilerplate ratio across site; duplicate titles/metas detected | **Gap**: No full exact/near-duplicate page pair detection. **Action**: Add minhash/LSH for near-duplicate detection across all page text; flag pages with >85% content overlap. |
| 18. Tags/Archives/Search | **NEW_AUTO** | None | **Action**: Detect common WP patterns (`/tag/`, `/category/`, `/author/`, `/?s=`, `/search/`); check meta robots, canonical, content word count for each pattern group; report indexability status. |
| 52. Cannibalization | **NEW_EXTERNAL_DATA** | None | **Requires**: GSC Query→Pages data + Semrush. **Action**: Build cannibalization detector using GSC merge data — flag when ≥2 URLs rank for the same query in positions 1–20. |
| 53. Search Intent | **NEW_MANUAL** | Cannot automate | Human review required. Provide SERP screenshot data and keyword clustering to assist. |
| 54. Keyword Map | **NEW_MANUAL** | Cannot automate | Strategic deliverable. Provide GSC Query×Page matrix as input. |
| 55. Content Value | **NEW_MANUAL** | Cannot automate | Human content review required. AI-tell detection from content_audit provides partial signal. |
| 56. Content Freshness | **NEW_MANUAL** | Cannot automate | Auto-detect year strings (`©2020`) and flag outdated-looking dates; final assessment requires human product knowledge. |

### Category: 技术性能 (Technical Performance) — Rules 19–23, 61–63

| Rule | Status | Current Implementation | Gaps & Actions |
|------|--------|----------------------|----------------|
| 19. Core Web Vitals | **EXISTING_PARTIAL** | 3 PSI tools exist (single/batch/all-crawl) with field_data_cwv + lab_data | **Gap**: Not auto-wired into chunked audit pipeline. **Action**: Wire PageSpeedDataProvider into finalize; add CWV section to MD report; run PSI on key templates (not all pages, for quota efficiency). |
| 20. TTFB | **EXISTING_PARTIAL** | `response_time_ms` per page (total time, not TTFB specifically) | **Gap**: No TTFB-specific measurement, no geographic distribution, no cache-hit vs cache-miss breakdown. **Action**: Add response header timing analysis; flag pages with response_time > 600ms as slow. |
| 21. Render-Blocking | **NEW_EXTERNAL_DATA** | None | **Requires**: PageSpeed API renderBlockingResources audit. **Action**: Parse PSI diagnostics into per-domain script/stylesheet blocking summary. |
| 22. Image Optimization | **EXISTING_PARTIAL** | 5 image checks: lazy-load, srcset, dimensions, next-gen format, alt text | **Gap**: No PSI image optimization opportunities integrated (Properly Size Images, Efficiently Encode Images). **Action**: Merge PSI image opportunities with existing image check findings. |
| 23. Caching & CDN | **EXISTING_PARTIAL** | `response_time_ms` indirect indicator only | **Gap**: No Cache-Control, CDN-Cache-Status, Age header analysis. **Action**: Add header-based cache audit: parse Cache-Control max-age/s-maxage; detect CDN markers (CF-Cache-Status, X-Cache, CDN-Loop, X-Drupal-Cache, etc.); flag static resources with TTL < 7 days. |
| 61. Field vs Lab Data | **EXISTING_PARTIAL** | PSI tools return both datasets but report doesn't distinguish | **Action**: In auto-wired PSI integration, clearly separate "Real User (CrUX)" and "Lab (Lighthouse)" sections. |
| 62. Third-Party Scripts | **NEW_EXTERNAL_DATA** | None | **Requires**: PSI third-party diagnostics. **Action**: Parse thirdPartySummary; compute per-third-party byte cost + main-thread blocking time. |
| 63. Font Loading & CLS | **NEW_EXTERNAL_DATA** | None | **Requires**: PSI CLS diagnostics + Lighthouse font-display audit. **Action**: Additionally parse in-HTML font-face declarations; check for font-display:swap; flag Google Fonts loaded without display=swap. |

### Category: 移动体验 (Mobile UX) — Rule 24

| Rule | Status | Current Implementation | Gaps & Actions |
|------|--------|----------------------|----------------|
| 24. Mobile Usability | **NEW_EXTERNAL_DATA** | Viewport meta tag existence check only | **Requires**: PSI Lighthouse mobile audit + CrUX mobile data. **Action**: Add mobile-ux section to report; integrate PSI mobile score, tap target sizing, font sizing, viewport configuration; flag missing viewport (already exists) + non-responsive viewport values. |

### Category: 安全与 Header (Security & Headers) — Rules 25–26

| Rule | Status | Current Implementation | Gaps & Actions |
|------|--------|----------------------|----------------|
| 25. HTTPS & Certificate | **EXISTING_PARTIAL** | HTTPS redirect + Mixed Content detection (http:// src/href in HTTPS pages) | **Gap**: No SSL certificate chain validation, no expiry date check, no mixed content from CSS/JS files. **Action**: Add certificate expiry check via httpx TLS info; add `cert_expiring_soon` rule (30/60/90 day thresholds). |
| 26. HSTS & Security Headers | **EXISTING_FULL** | All 5 security headers: HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy | None — complete. |

### Category: 结构化数据 (Structured Data) — Rules 27–28, 78

| Rule | Status | Current Implementation | Gaps & Actions |
|------|--------|----------------------|----------------|
| 27. Schema Coverage | **EXISTING_FULL** | 17 schema types validated; @graph parsing (Yoast/RankMath/WPRM); type-level coverage statistics | None — complete. |
| 28. Schema Conflicts | **EXISTING_PARTIAL** | Required field validation + parse errors detected | **Gap**: No multi-plugin conflict detection. **Action**: Compare multiple JSON-LD blocks on same page; flag duplicate @type with different @id values; detect Organization entity mismatch across plugins. |
| 78. Schema vs Visible Content | **EXISTING_PARTIAL** | Structural validation only — no content comparison | **Gap**: Cannot verify schema claims against visible page content. **Action**: Extract key schema values (price, rating, availability, name, address) and compare with extracted visible content; flag discrepancies. |

### Category: 国际化 / 多语言 (International) — Rules 29, 58–60

| Rule | Status | Current Implementation | Gaps & Actions |
|------|--------|----------------------|----------------|
| 29. hreflang Basics | **EXISTING_FULL** | 8 hreflang checks: self-reference, x-default, invalid codes, missing return tags, lang-attr conflicts, to_broken, to_noindex | None — complete. |
| 58. hreflang Indexability | **EXISTING_FULL** | `hreflang_to_noindex` + `hreflang_to_broken` + cross-checks for 200+indexable+self-canonical | None — complete. |
| 59. Language/Code Match | **EXISTING_PARTIAL** | `hreflang_invalid_codes` + `hreflang_conflicts_lang_attr` checked | **Gap**: No actual page content language detection. **Action**: Add optional language detection (langdetect/cld3) for pages to compare declared language with detected content language; flag known machine-translation patterns (mixed language, residual source text). |
| 60. Multi-Language Canonical | **NEW_AUTO** | None | **Action**: Detect URL language patterns (`/en/`, `/de/`, `/zh/`, `en.`, `de.`); check if non-default-language pages canonical to default language; flag for self-canonical correction. |

### Category: 链接分析 (Link Analysis) — Rules 30–31, 77

| Rule | Status | Current Implementation | Gaps & Actions |
|------|--------|----------------------|----------------|
| 30. Broken Internal Links | **EXISTING_FULL** | "Broken Pages" table with Linked From + anchor text; inlinks to 4xx pages tracked | None — complete. |
| 31. Backlink Overview | **NEW_EXTERNAL_DATA** | None | **Requires**: Semrush Backlink Analytics API or GSC Links report. **Action**: Build SemrushDataProvider; add backlink summary section showing refdomains, top-linked pages, new/lost trend. |
| 77. Lost Backlinks | **NEW_EXTERNAL_DATA** | None | **Requires**: Semrush Lost Backlinks report by URL. **Action**: Cross-reference with GSC declining pages to identify ranking drops potentially caused by link loss. |

### Category: JavaScript SEO — Rules 46–48

| Rule | Status | Current Implementation | Gaps & Actions |
|------|--------|----------------------|----------------|
| 46. Rendered Content | **NEW_EXTERNAL_DATA** | None — Playwright explicitly removed from roadmap (v1.8.0) | **Requires**: Playwright (~300MB) or GSC URL Inspection rendering. **Action**: Lightweight approach: compare raw HTML text length vs expected; flag pages where critical SEO elements (title/canonical/h1) are absent in raw HTML but might be JS-injected (detect `<div id="root">` / `<div id="app">` patterns); defer full JS rendering to optional Playwright provider. |
| 47. Crawlable `<a href>` Links | **NEW_AUTO** | None | **Action**: Analyze page HTML for navigation patterns without `<a href>`: detect onclick-based navigation in nav/menu elements; compute ratio of `<a href>` links vs event-handler-only interactive elements. |
| 48. Lazy-Load Indexability | **NEW_EXTERNAL_DATA** | None | **Requires**: JS rendering or GSC comparison. **Action**: Partial auto-detection: find "Load More" / "Show More" / infinite-scroll patterns; detect content hidden behind display:none containers; flag when main content area has `<button>` as the only additional content trigger. |

### Category: WordPress 专项 — Rules 36–39, 64–69

| Rule | Status | Current Implementation | Gaps & Actions |
|------|--------|----------------------|----------------|
| 36. WP Updates | **NEW_MANUAL** | Cannot automate from external scan | Partial external detection: parse `generator` meta tag for WP version; check readme.html for version exposure; flag if version < latest stable. Full plugin/theme inventory requires WP admin access. |
| 37. SEO Plugin Conflicts | **EXISTING_PARTIAL** | Schema conflicts partially detected | **Action**: Add WP-specific SEO output detection: check for multiple canonical links; detect Yoast+RanMath vs theme SEO vs caching plugin HTML comments markers; flag when >1 SEO plugin fingerprints found in page source. |
| 38. Permalink | **EXISTING_PARTIAL** | URL quality checks (spaces/slashes/underscores) exist | **Action**: Add `?p=123` parameter detection; analyze URL path structure consistency; flag mixed permalink patterns within same post type. |
| 39. XML-RPC/REST API | **NEW_AUTO** | None | **Action**: HTTP GET `/xmlrpc.php` — flag if reachable; GET `/wp-json/wp/v2/users` — flag if exposes user data; GET `/wp-login.php` — check for WAF/rate-limit headers. |
| 64. WP-Cron | **NEW_MANUAL** | Cannot automate | Would need server log access + WP-CLI. |
| 65. Database Bloat | **NEW_MANUAL** | Cannot automate | Would need DB access. |
| 66. Cache/CDN Synergy | **EXISTING_PARTIAL** | Indirect via response_time | **Action**: Same improvements as Rule 23 (Caching & CDN); add WP-specific cache header checks (WP Super Cache, W3 Total Cache, WP Rocket, Litespeed Cache markers). |
| 67. Staging Indexed | **NEW_AUTO** | None | **Action**: Detect common staging domains (staging.*, dev.*, *.staging.*, *.flywheelsites.com, *.wpengine.com, *.kinsta.cloud); check if they return noindex/require auth/are blocked; flag if indexable. |
| 68. Admin 2FA | **NEW_MANUAL** | Cannot automate | External check: test wp-login.php for WAF/rate-limit; check `/wp-content/plugins/` for 2FA plugin paths; partial detection possible. |
| 69. Abandoned Plugins | **NEW_MANUAL** | Cannot automate | Needs WP admin. External detection via plugin readme.txt path enumeration (unreliable). |

### Category: 监控与跟踪 (Monitoring & Tracking) — Rules 34–35, 72–74, 80

| Rule | Status | Current Implementation | Gaps & Actions |
|------|--------|----------------------|----------------|
| 34. GSC/GA4 Config | **NEW_EXTERNAL_DATA** | GSC merge tool exists (data-fed, not direct API) | **Requires**: GSC + GA4 property admin access. **Action**: Build GSCAdminProvider for property/verification/sitemap status checks; GA4AdminProvider for data stream validation. |
| 35. Conversion Tracking | **NEW_EXTERNAL_DATA** | None | **Requires**: GA4/GTM access. **Action**: Detect common GTM/GA4 snippet presence; flag pages with forms but no visible analytics event handlers (partial detection only). |
| 72. Manual Actions | **NEW_MANUAL** | None | **Requires**: Manual verification in Google Search Console UI. Current Search Console API does NOT expose Manual Actions / Security Issues via automated endpoints. Automated run: `execution_status = NOT_CHECKED`, reason: *"Requires manual verification in Google Search Console UI; no supported Search Console API endpoint configured."* Do NOT fabricate a PASS. |
| 73. SEO Change Log | **NEW_MANUAL** | Cannot automate | Process item. Provide GSC ranking/impression trend data as input for change log correlation. |
| 74. Regression Testing | **NEW_AUTO** | None | **Action**: Build crawl diff engine: run two audits (before/after), compare: new/missing URLs, status code changes, title/H1/canonical/robots/schema deltas. Generate regression report as separate artifact. This is a unique feature with high value. |
| 80. Availability Monitoring | **NEW_EXTERNAL_DATA** | None | **Requires**: External monitoring service (UptimeRobot API, or built-in periodic check). **Action**: Add lightweight internal uptime check: schedule HEAD request to key URLs every 5 minutes during audit window; report any intermittent failures. |

### Category: 其他 (Others) — Rules 32, 33, 40, 53–57, 70–71, 75–76, 79

| Rule | Status | Current Implementation | Gaps & Actions |
|------|--------|----------------------|----------------|
| 32. Media Sitemap | **NEW_AUTO** | None | Check sitemap index for image/video namespace entries; provide recommendation based on site type. |
| 33. Server Log Analysis | **NEW_EXTERNAL_DATA** | None | **Requires**: Server log file access. Build log parser for Apache/Nginx combined format; compute Googlebot hit frequency, status distribution, top crawled paths, wasted crawl. |
| 40. Audit Deliverables | **EXISTING_PARTIAL** | Fix Priority Checklist in MD report | Add machine-readable task export (CSV with columns: id, rule, priority, finding_count, owner, remediation, acceptance_criteria, status); add Jira CSV import format. |
| 53–57 | (See Content sections above) | Mixed NEW_MANUAL | — |
| 70. Form Accessibility | **EXISTING_PARTIAL** | anchor/iframe/image ALT checks exist | Add form-specific checks: label/aria-label presence, required field markers, submit button accessible name, empty form action detection. |
| 71. Form E2E | **NEW_MANUAL** | Cannot automate (real submission) | Partial: detect form action URL validity, required field indicators, CAPTCHA presence, form method; generate a manual test checklist per form detected. |
| 75. Device/Country Ranking | **NEW_EXTERNAL_DATA** | None | Requires GSC Country/Device dimensions + Semrush Position Tracking. |
| 76. Declining Pages↔Keywords | **NEW_EXTERNAL_DATA** | None | Requires GSC Query×Page 28-day comparison. Build decline mapper as extension of existing GSC merge tool. |
| 79. Image ALT/Link Quality | **EXISTING_PARTIAL** | 6 image checks exist | Add ALT quality heuristic: keyword-stuffed ALT detection, description-length ALT check (<5 chars or >125 chars), image-link context verification. |

---

## Severity Consolidation Map

The existing system has 4 different severity schemes. The unified taxonomy:

| Unified Severity | v3.0 Code | Maps From | Use in Report |
|---|---|---|---|
| **Error** | `SEVERITY_ERROR` | Critical section, `"high"`, `broken_classes` | Red — blocks indexing, ranking, or user experience |
| **Warning** | `SEVERITY_WARNING` | Warnings section, `"medium"` | Amber — degrades performance, may impact ranking |
| **Opportunity** | `SEVERITY_OPPORTUNITY` | `"low"`, content_audit thresholds | Blue — improvement opportunity, not currently broken |
| **Info** | `SEVERITY_INFO` | (new) | Gray — informational finding, no action required |

---

## Data Provider Availability Matrix

| Provider | Required For Rules | Auto-Wired in Chunked Audit? | Fallback When Unavailable |
|----------|-------------------|:---------------------------:|---------------------------|
| LibreCrawl (core) | 68 rules | ✅ Always | N/A (required) |
| PageSpeed API | 19, 21, 22, 24, 61, 62, 63 | ❌ → ✅ (Phase 3) | Skip PSI-dependent rules; mark NOT_CHECKED |
| GSC API | 2, 44, 52, 72, 75, 76 | ❌ (data-fed only) | GSC rules marked NOT_CHECKED unless data is fed |
| Semrush API | 31, 52, 75, 77 | ❌ → 🔌 (Phase 5) | Semrush rules marked NOT_CHECKED |
| GA4 / GTM | 34, 35 | ❌ | GA4 rules marked NOT_CHECKED |
| Server Logs | 5, 33 | ❌ → 🔌 (Phase 6) | Log-based rules marked NOT_CHECKED |
| WordPress Admin | 36, 64, 65, 68, 69 | ❌ | Wordpress rules marked NOT_APPLICABLE or NOT_CHECKED |
| Manual Review | 53, 54, 55, 56, 57, 71, 73 | N/A | Always NOT_CHECKED in automated pass; provides guidance |
