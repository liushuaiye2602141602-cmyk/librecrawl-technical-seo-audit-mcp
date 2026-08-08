# Implementation Plan — Enterprise SEO Audit v3.0.0

> **Date**: 2026-08-09 | **Phases**: 8 | **Estimated Total Effort**: ~45–60 developer-days  
> **Status**: AWAITING APPROVAL — No code has been modified

---

## Phase Structure Overview

```
Phase 1  ████████░░░░░░░░░░░░░░░░░░░░  Foundation: Registry + PageContext
Phase 2  ████████████████░░░░░░░░░░░░  Enhance EXISTING_PARTIAL (24 rules)
Phase 3  ████████████████████████░░░░  Wire External Providers (PSI, Cache Headers)
Phase 4  ████████████████████████████  Implement NEW_AUTO (9 rules)
Phase 5  ██████████████████████████████  GSC + Semrush Integration (8 rules)
Phase 6  ██████████████████████████████  Server Logs + WP Detection (4 rules)
Phase 7  ██████████████████████████████  Regression Testing Engine (1 rule)
Phase 8  ██████████████████████████████  Docs, Tests, Migration, Release
```

---

## Phase 1: Foundation — Rule Registry + PageContext + Coverage Manager

**Files to create:**
- `audit_rules/__init__.py`
- `audit_rules/registry.py` — 80 `RuleDefinition` dataclass instances
- `audit_rules/categories.py` — Category/Priority/FindingType/DataSource/DetectionMethod enums
- `audit_rules/severity.py` — Unified severity taxonomy (Error/Warning/Opportunity/Info)
- `audit_rules/context.py` — PageContext + SiteContext dataclasses with lazy-caching
- `audit_rules/runner.py` — RuleRunner + CoverageManager
- `audit_rules/providers/__init__.py`
- `audit_rules/providers/base.py` — DataProvider ABC
- `audit_rules/providers/librecrawl_provider.py` — Core crawl data (always available)

**Files to modify:**
- `server.py` — Import registry; keep existing checks (no removal yet); add coverage report tool
- `runner.py` — Import RuleRunner; add coverage computation to `_finalize_session`
- `state.py` — **NOT modified in Phase 1** (audit score tables deferred to Phase 7)

**Acceptance criteria:**
- [ ] All 80 rules loaded from CSV (checklist + mapping) into registry with validation
- [ ] `PageContext` uses lightweight fields from existing export data; no re-fetch; heavy fields lazy-loaded
- [ ] `RuleRunner` evaluates 18 EXISTING_FULL rules via adapter/binding to existing logic
- [ ] `CoverageManager` generates exactly 80 CoverageRow entries with ExecutionStatus + ResultStatus split
- [ ] Existing 8-file zip is produced unchanged (backward compatibility verified)
- [ ] New `coverage.csv` appears in zip as 9th file (exactly 80 rows, rule-level)
- [ ] No `audit-score.json` in Phase 1 (deferred to Phase 7)
- [ ] No regressions on test domains (baolaipackaging.com serves as smoke test)

**Risk:** High (foundational refactor). **Mitigation:** Phase 1 does NOT remove any existing check code. It runs in parallel — the registry produces coverage data while the existing `_build_report` path remains the source of truth for MD/CSV output. Only after Phase 1 produces identical results do later phases begin migrating checks.

---

## Phase 2: Enhance EXISTING_PARTIAL — 24 Rules to Full Coverage

**Files to create:**
- `checks/__init__.py`
- `checks/crawl_index.py` — Rules 2, 5: Sitemap GSC status, crawl budget enhancements
- `checks/site_architecture.py` — Rules 10, 12: Breadcrumb HTML detection, pagination audit
- `checks/content_metadata.py` — Rules 13, 16, 17: CTR integration, near-duplicate detection, tag/archive patterns
- `checks/technical_performance.py` — Rules 20, 22, 23: Cache header audit, image optimization summary
- `checks/url_redirect.py` — Rules 49, 50, 51: URL normalization expansion, redirect relevance heuristics, internal links→redirects
- `checks/structured_data.py` — Rules 28, 78: Schema conflict detection, schema-vs-content comparison
- `checks/international.py` — Rules 59, 60: Language detection, multi-language canonical
- `checks/wordpress.py` — Rules 37, 38, 66: SEO plugin conflict, permalink, cache synergy
- `checks/conversion.py` — Rule 70: Form accessibility (label, aria, button checks)

**Files to modify:**
- `extended_checks.py` — Begin deprecation: each migrated check adds a deprecation warning referencing the new `checks/*.py` location
- `content_audit.py` — Extend with near-duplicate detection via minhash
- `server.py` — Wire new checks into report sections

**Acceptance criteria:**
- [ ] 24 EXISTING_PARTIAL rules promoted to EXISTING_FULL in registry
- [ ] Cache-Control/CDN header audit produces per-page cache status
- [ ] Near-duplicate content detection identifies page pairs with >85% overlap
- [ ] Breadcrumb HTML detection matches visual breadcrumbs to schema BreadcrumbList
- [ ] Pagination audit detects rel=next/prev and validates self-canonical strategy
- [ ] URL normalization expanded from 4 to 8 quality dimensions
- [ ] Redirect relevance heuristics flag suspicious patterns (bulk→homepage, wrong-language)
- [ ] Schema-vs-content comparison works for price/rating/name/address fields
- [ ] Form accessibility audit checks label/aria/button/action attributes
- [ ] All enhanced checks have HTML fixture tests (offline-verifiable)

---

## Phase 3: Wire External Data Providers — PageSpeed + Cache + SSL

**Files to create:**
- `audit_rules/providers/pagespeed_provider.py` — PageSpeedDataProvider
- `checks/technical_performance.py` — CWV section (Rule 19), render-blocking (Rule 21), third-party (Rule 62)
- `checks/mobile_ux.py` — Rule 24: Mobile usability from PSI data
- `checks/security_headers.py` — Rule 25: SSL certificate expiry check

**Files to modify:**
- `runner.py` — Wire PageSpeedDataProvider into finalize; add configurable `psi_sample` (default: top 20 pages by internal links, not all pages)
- `server.py` — Update `_build_report` with CWV section, mobile UX section, third-party impact
- `pdf_report.py` — Add CWV score card visual to PDF

**Acceptance criteria:**
- [ ] After chunked audit completes, PSI auto-fires on key template pages
- [ ] CWV section in MD + PDF: Field Data (CrUX) + Lab Data (Lighthouse) per template
- [ ] Third-party script cost summary (bytes + main-thread time per provider)
- [ ] SSL certificate expiry check with severity based on remaining days
- [ ] When `PAGESPEED_API_KEY` is absent, PSI-dependent rules gracefully marked NOT_CHECKED
- [ ] PSI rate limit respected: minimum 1.1s between calls, max 25 URLs per batch

---

## Phase 4: Implement NEW_AUTO — 9 Rules from Scratch

**Files to create/modify:**
- `checks/crawl_index.py` — Rule 43: sitemap lastmod anomaly detection
- `checks/content_metadata.py` — Rule 18: tag/archive/search page indexability audit
- `checks/wordpress.py` — Rules 32, 39, 67: Media sitemap check, XML-RPC/REST API detection, staging site indexability
- `checks/url_redirect.py` — Rule 51: internal links pointing to redirects (cross-reference)
- `checks/js_seo.py` — Rule 47: `<a href>` vs onclick navigation detection
- `checks/international.py` — Rule 60: multi-language canonical strategy audit
- `checks/monitoring.py` — Rule 74: pre/post regression crawl diff engine

**Acceptance criteria:**
- [ ] 9 NEW_AUTO rules all have registry functions + HTML fixture tests
- [ ] Sitemap lastmod anomaly detection catches: all-same-date, future-dates, daily-bulk-refresh
- [ ] Tag/archive/search page patterns detected for WordPress, Shopify, and generic CMS
- [ ] XML-RPC/REST API endpoints tested with rate-limit/WAF detection
- [ ] Staging site detection covers common patterns and checks indexability
- [ ] Internal-links→redirects cross-reference produces actionable fix list
- [ ] `<a href>` vs onclick navigation ratio computed per page
- [ ] Multi-language canonical checker flags wrong-language canonicals
- [ ] Crawl diff engine produces before/after delta report with new/missing/changed URLs

---

## Phase 5: GSC + Semrush Integration — 8 Rules via External APIs

**Files to create:**
- `audit_rules/providers/gsc_provider.py` — GSCDataProvider (direct API, not just data-fed)
- `audit_rules/providers/semrush_provider.py` — SemrushDataProvider
- `audit_rules/providers/ga4_provider.py` — GA4DataProvider

**Files to modify:**
- `server.py` — New MCP tools: `librecrawl_connect_gsc`, `librecrawl_connect_semrush`, `librecrawl_provider_status`
- `checks/crawl_index.py` — Rule 44: Google-selected canonical vs user-declared (via GSC URL Inspection)
- `checks/content_metadata.py` — Rule 52: keyword cannibalization detector (via GSC Query×Page)
- `checks/link_analysis.py` — Rules 31, 77: backlink overview, lost backlinks (via Semrush)
- `checks/monitoring.py` — Rules 34, 35, 72, 75, 76: GSC admin, conversion tracking, manual actions, ranking splits, decline mapping

**Acceptance criteria:**
- [ ] GSCDataProvider auto-fetches: sitemap status, index coverage, manual actions, top queries per page
- [ ] SemrushDataProvider fetches: domain backlinks, referring domains, lost backlinks
- [ ] Cannibalization detector flags ≥2 URLs ranking 1–20 for same query
- [ ] Google-selected canonical mismatches surfaced for P0 pages
- [ ] Provider status tool reports: which providers are configured, which rules they unlock
- [ ] Rate limits documented and respected for each API
- [ ] All 17 EXISTING_EXTERNAL_DATA rules produce either real data or explicit NOT_CHECKED with reason

---

## Phase 6: Server Logs + WordPress Detection — Remaining External Rules

**Files to create:**
- `audit_rules/providers/server_log_provider.py` — ServerLogDataProvider
- `checks/wordpress.py` — Rule 36: WP version detection (via generator meta, readme.html)

**Files to modify:**
- `checks/crawl_index.py` — Rule 5, 33: Crawl budget from logs, Googlebot crawl analysis

**Acceptance criteria:**
- [ ] ServerLogDataProvider parses Apache Combined + Nginx Combined formats
- [ ] Googlebot crawl stats: requests/day, status distribution, top crawled paths, wasted crawl %
- [ ] WP version detection from external signals (generator tag, readme.html hash comparison)
- [ ] Fallback gracefully when log files are absent or unreadable (NOT_CHECKED)

---

## Phase 7: Unique Features — Regression Testing + Audit Score

**Files to create:**
- `checks/monitoring.py` — Rule 74: Pre/post crawl diff engine (finalize)
- `audit_rules/scoring.py` — Weighted audit score calculator

**Acceptance criteria:**
- [ ] Crawl diff accepts two session IDs and produces:
  - New URLs (found in post but not pre)
  - Missing URLs (found in pre but not post)
  - Changed URLs: status code / title / H1 / canonical / robots / schema delta per URL
  - Summary: counts of new issues introduced, fixed, unchanged
- [ ] Audit score: weighted score per category + overall 0–100 score with breakdown
- [ ] Regression workflow: `librecrawl_start_chunked_audit("staging.example.com")` → make changes → `librecrawl_start_chunked_audit("staging.example.com")` → `librecrawl_crawl_diff(sid1, sid2)`

---

## Phase 8: Documentation, Testing, Migration, Release

**Files to create:**
- `tests/fixtures/html/` — 30+ HTML fixtures (one per check category)
- `tests/fixtures/pages/` — Mock LibreCrawl export JSON files
- `tests/fixtures/sitemaps/` — Sample sitemap XML files
- `tests/test_registry.py` — All 80 rules have valid definitions, unique IDs, consistent categories
- `tests/test_runner.py` — RuleRunner evaluates each fixture correctly (at least 10 fixture→expected findings tests)
- `tests/test_providers.py` — Mock provider responses return correct enrichments
- `tests/test_coverage.py` — Coverage matrix generation for complete + partial audits
- `docs/audit/` — (already created in Phase 1 analysis)
- `docs/UPGRADE-v2-to-v3.md` — Migration guide for existing deployments

**Files to modify:**
- `README.md` — Update feature matrix (80 rules), new architecture summary
- `CHANGELOG.md` — v3.0.0 entry
- `docker-compose.yml` — Add env vars for new providers (PAGESPEED_API_KEY, SEMRUSH_API_KEY, etc.)
- `requirements.txt` — Add minhash, langdetect, dnspython (lightweight additions only)

**Acceptance criteria:**
- [ ] `pytest tests/` passes 100% on all fixtures (no live internet required)
- [ ] Smoke test: full audit of baolaipackaging.com with v3.0.0 → identical core findings to v2.2.0 + new coverage report
- [ ] Docker Compose deployment tested on clean Ubuntu + Windows (Docker Desktop)
- [ ] All 37 MCP tool signatures preserved + 5 new tools added
- [ ] README updated with 80-rule coverage table
- [ ] v3.0.0 git tag + GitHub release

---

## Files to Modify — Complete Inventory

| File | Phase | Change Type | Risk |
|------|:-----:|-------------|:----:|
| `server.py` | 1–5 | Add registry import, coverage tool, new report sections, GSC/Semrush tools | **HIGH** |
| `runner.py` | 1–3 | RuleRunner integration, PSI auto-wiring | **HIGH** |
| `state.py` | — | **NOT modified in Phase 1** | — |
| `extended_checks.py` | 2 | Deprecation wrappers → gradual phase-out | MEDIUM |
| `content_audit.py` | 2 | Near-duplicate detection via minhash | MEDIUM |
| `schema_validator.py` | 2 | Schema-vs-content comparison | MEDIUM |
| `external_links.py` | 2 | Registry-backed severity; no format change | LOW |
| `pdf_report.py` | 3 | CWV score card visual | LOW |
| `README.md` | 8 | 80-rule feature matrix | LOW |
| `CHANGELOG.md` | 8 | v3.0.0 entry | LOW |
| `docker-compose.yml` | 8 | New provider env vars | LOW |
| `requirements.txt` | 8 | minhash, langdetect, dnspython | LOW |

## Files to Create — Complete Inventory

| File | Phase | Purpose |
|------|:-----:|---------|
| `audit_rules/registry.py` | 1 | 80 RuleDefinition instances |
| `audit_rules/categories.py` | 1 | Enums |
| `audit_rules/severity.py` | 1 | Unified severity taxonomy |
| `audit_rules/context.py` | 1 | PageContext + SiteContext |
| `audit_rules/runner.py` | 1 | RuleRunner + CoverageManager |
| `audit_rules/providers/base.py` | 1 | DataProvider ABC |
| `audit_rules/providers/librecrawl_provider.py` | 1 | Core crawl data |
| `audit_rules/providers/pagespeed_provider.py` | 3 | PSI API adapter |
| `audit_rules/providers/gsc_provider.py` | 5 | GSC API adapter |
| `audit_rules/providers/semrush_provider.py` | 5 | Semrush API adapter |
| `audit_rules/providers/ga4_provider.py` | 5 | GA4 API adapter |
| `audit_rules/providers/server_log_provider.py` | 6 | Server log parser |
| `audit_rules/scoring.py` | 7 | Weighted audit score |
| `checks/crawl_index.py` | 2,4,6 | Rules 1–5, 41–45 |
| `checks/url_redirect.py` | 2,4 | Rules 6–8, 49–51 |
| `checks/site_architecture.py` | 2 | Rules 9–12 |
| `checks/content_metadata.py` | 2,4,5 | Rules 13–18, 52–56 |
| `checks/technical_performance.py` | 2,3 | Rules 19–23, 61–63 |
| `checks/mobile_ux.py` | 3 | Rule 24 |
| `checks/security_headers.py` | 2,3 | Rules 25–26 |
| `checks/structured_data.py` | 2 | Rules 27–28, 78 |
| `checks/international.py` | 2,4 | Rules 29, 58–60 |
| `checks/link_analysis.py` | 5 | Rules 30–31, 77 |
| `checks/js_seo.py` | 4 | Rules 46–48 |
| `checks/wordpress.py` | 2,4,6 | Rules 32, 36–39, 64–69 |
| `checks/conversion.py` | 2 | Rules 70–71 |
| `checks/monitoring.py` | 4,5,7 | Rules 34–35, 72–76, 80 |
| `checks/trust_eeat.py` | (future) | Rule 57 |
| `tests/fixtures/html/*.html` | 8 | 30+ test fixtures |
| `tests/fixtures/pages/*.json` | 8 | Mock crawl exports |
| `tests/fixtures/sitemaps/*.xml` | 8 | Sample sitemaps |
| `tests/test_*.py` | 8 | Unit tests |
| `docs/UPGRADE-v2-to-v3.md` | 8 | Migration guide |

---

## Migration Risk Assessment

| Risk | Severity | Mitigation |
|------|:--------:|------------|
| **Check regression** — migrated checks produce different results than original code | **HIGH** | Side-by-side run on 3 known domains; diff every CSV column; require 100% match on EXISTING_FULL rules |
| **Performance regression** — PageContext caching adds memory; near-duplicate detection adds CPU | MEDIUM | Use streaming batch processing for large page sets; benchmark on 1900+ page site |
| **Import cycle hell** — 15 new modules risk circular imports | MEDIUM | Enforce dependency direction: registry ← providers ← checks ← runner ← server (one-way) |
| **API rate limit exhaustion** — PSI + GSC + Semrush all hitting APIs during one finalize | MEDIUM | Configurable delays; sampling strategy for large sites; graceful NOT_CHECKED instead of failure |
| **Environment fragmentation** — not all deployments have all API keys | LOW | Each provider self-tests availability; missing providers → NOT_CHECKED for their rules, not error |
| **Docker image size** — new deps (minhash, langdetect, dnspython) add ~10MB | LOW | All are pure Python or have prebuilt wheels; no system library changes |

---

## Test Plan Summary

### Unit Tests (offline, no live internet)
- **Registry integrity**: All 80 rules have unique IDs, valid categories, consistent severity
- **Rule functions**: Each EXISTING_FULL + EXISTING_PARTIAL + NEW_AUTO rule tested with hand-crafted HTML fixtures
- **PageContext**: Caching behavior, lazy loading, cross-page shingle computation
- **CoverageManager**: Correct status assignment for all 5 states
- **DataProvider mocks**: Each adapter returns correct enrichment shape

### Integration Tests (controlled live environment)
- **PSI adapter**: Real API call with known URL, verify returned data structure
- **Crawl diff**: Two known page sets, verify correct delta
- **Zip integrity**: All 10 files present, correct format, SUMMARY.txt accurate

### Smoke Tests (production-like)
- Full audit of baolaipackaging.com (311 pages) — v2.2.0 vs v3.0.0 diff
- Full audit of a 1-page site (edge case)
- Full audit with all providers unavailable (graceful degradation)
- Docker Compose deployment on clean environment

---

## Approval Gates

After each phase, the following must be confirmed before proceeding:

| Phase | Gate |
|:-----:|------|
| 1 | Registry definitions correct; PageContext produces identical data to existing code; coverage matrix generates without errors; backward compatibility verified on 1 real domain |
| 2 | All 24 enhanced rules produce findings; no regression on 3 test domains; HTML fixture tests pass |
| 3 | PSI auto-wired into audit pipeline; CWV section appears in MD+PDF; graceful NOT_CHECKED when API key absent |
| 4 | All 9 NEW_AUTO rules produce findings on test fixtures; no false positives on test domains |
| 5 | GSC/Semrush providers successfully enrich PageContext; cannibalization detector identifies known cases |
| 6 | Server log parser handles Apache+Nginx formats; WP version detection works from external signals |
| 7 | Crawl diff produces accurate before/after delta; audit score correlates with known site quality |
| 8 | Full test suite passes; Docker deployment verified; documentation complete; smoke test on 3 domains |

---

## Summary: What the User Should Approve

1. **Phase 1 first** — Do not start coding until the architecture and registry design is approved
2. **Current capability**: ~55 fragmented checks → **80 precisely defined rules** with unified taxonomy
3. **Full automation target**: 67/80 rules (83.75%) at least partially automated (18 EXISTING_FULL + 24 EXISTING_PARTIAL + 9 NEW_AUTO + 16 NEW_EXTERNAL_DATA)
4. **External dependencies**: 16 rules (20%) require external data (PageSpeed API key already available; GSC/Semrush/GA4/Server Logs optional)
5. **Manual-only**: 13 rules (16.25%) that require human review — the system provides guidance but can't replace human judgment
6. **Backward compatible**: Existing MCP tools, CSV formats, and zip structure preserved
7. **Offline-testable**: All automated rules verifiable with HTML fixtures — no live internet needed in CI

---

*End of Implementation Plan. Await approval before writing any code.*
