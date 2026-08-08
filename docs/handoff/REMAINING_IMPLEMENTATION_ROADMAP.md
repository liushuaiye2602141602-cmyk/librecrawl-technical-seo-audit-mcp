# Remaining Implementation Roadmap — Codex Handoff

**Date:** 2026-08-09
**Current checkpoint:** 48 adapters, 514 tests passing after PSI live validation, commit `aba10ce`
**Goal:** 80/80 rules fully implemented, all providers live-validated, ≥1,200 tests
**Related:** [CURRENT_RULE_MATRIX.csv](CURRENT_RULE_MATRIX.csv) | [BLOCKERS_AND_CREDENTIALS.md](BLOCKERS_AND_CREDENTIALS.md)

---

## Overview: 12 Workstreams

```
Phase 4B (WS1) ────► PSI Validation (WS2) ──┬──► GSC Provider (WS4) ──► GSC Rules (WS10a)
                                              ├──► Semrush Provider (WS5) ──► Semrush Rules (WS10b)
                                              ├──► Server Log Provider (WS6) ──► Log Rules (WS10c)
                                              ├──► GA4 Provider (WS7) ──► GA4 Rules (WS10d)
                                              └──► WP Provider (WS8) ──► WP Rules (WS10e)

PARTIAL Gap Closure (WS3) ────► Manual Review (WS9) ────► Audit Score (WS11) ────► Integration (WS12)
```

**Parallelism opportunity:** Workstreams 4–8 (all providers) can run in parallel since they're independent. Workstream 3 (PARTIAL gap closure) is also parallel to provider work. Workstream 10 (NEW_EXTERNAL_DATA rules) depends on the corresponding provider being done.

---

## Workstream 1: Phase 4B — Rule 74 (Snapshot Diff)

**Status:** COMPLETE on 2026-08-09. See `docs/audit/PHASE4B_COMPLETION_REPORT.md`.
**Priority:** Completed
**Depends on:** Nothing (stateless except for snapshot storage)
**Unlocks:** 1 rule → brings NEW_AUTO from 1 → 0

### 1.1 What Rule 74 Does
"Content Score Audit" — compares current audit findings against a previous audit snapshot, detects regressions (lost URLs, status changes, Title/H1/canonical drift, schema changes, new errors).

### 1.2 Implementation Steps

1. **Design snapshot storage format** — JSON file per audit: `snapshots/<domain>_<timestamp>.json`
   ```json
   {
     "audit_id": "uuid",
     "domain": "example.com",
     "timestamp": "2026-08-09T00:00:00Z",
     "pages": {
       "/page1": {"status": 200, "title": "...", "h1": "...", "canonical": "...", "schema_types": [...]},
       ...
     },
     "aggregates": {
       "total_pages": 500,
       "error_count": 12,
       "warning_count": 45,
       ...
     }
   }
   ```

2. **Implement snapshot writer** — `audit_rules/snapshot.py`
   - `save_snapshot(site_ctx, page_contexts, findings, output_dir)` → writes JSON
   - `load_snapshot(path)` → returns parsed dict
   - `find_previous_snapshot(domain, snapshots_dir)` → returns most recent non-current

3. **Implement diff engine** — `audit_rules/snapshot.py`
   - Page-level diff: new pages, removed pages, status changes (200→404, 200→301, etc.)
   - Metadata diff: Title change >30%, H1 change >50%, canonical URL change, schema type change
   - Aggregate diff: error/warning count delta, new issue categories

4. **Implement check function** — `check_content_score_audit()` in `audit_rules/checks/snapshot_diff.py`
   - Loads previous snapshot, runs diff, produces Finding for each significant change
   - Severity: Error (new 404s, lost pages), Warning (Title/H1 drift), Info (new pages detected)

5. **Register adapter** in `audit_rules/adapters.py`

6. **Write tests** — `tests/phase4b/test_snapshot_diff.py`
   - Two snapshots: before/after → verify diffs detected
   - No previous snapshot → empty findings (graceful)
   - Identical snapshots → empty findings
   - Edge: empty previous, empty current, large scale (1000+ pages)

7. **Update CSV:** Rule 74: `NEW_AUTO` → `EXISTING_PARTIAL` (PARTIAL because needs historical snapshot; first audit has no baseline)

### 1.3 Estimated Effort
~4-6 hours (snapshot format design, diff engine, check function, 15-20 tests)

### 1.4 Delivered state

The earlier session-ID/JSON sketch above is retained as historical planning
context and superseded by the portable `audit-snapshot-v1.json.gz` contract.
Rule 74 is now `EXISTING_PARTIAL`; `NEW_AUTO` is zero. A missing baseline is
`NOT_CHECKED + UNKNOWN`, while a validated identical baseline executes and can
PASS. The production finalize path registers both the current snapshot and,
when a baseline is valid, `crawl-diff.csv`.

---

## Workstream 2: PSI Provider Live Validation

**Status:** COMPLETE on 2026-08-09. Client, provider, and full V3 pipeline were
validated live against `https://example.com/`; see
`docs/audit/PHASE3_LIVE_VALIDATION_REPORT.md`.
**Priority:** Completed
**Depends on:** Credential present (PAGESPEED_API_KEY in .env)

### 2.1 Steps

1. **Smoke test `psi_client.py`** against a real domain with the existing key
   - Verify response parsing (CrUX field data, Lighthouse lab data)
   - Check error handling (quota exceeded, invalid key, no data)
   - Verify `PSI_SAMPLE_LIMIT` and `PSI_STRATEGIES` are respected

2. **Validate provider integration** — `pagespeed_provider.py`
   - Run `MasterAuditRunner` with `MASTER_AUDIT_PSI_ENABLED=true` on a test domain
   - Verify PSI data flows into performance check functions (19, 20, 21, 22, 24, 61, 62, 63)

3. **Write provider tests** — `tests/providers/test_psi_provider.py`
   - Mock PSI API responses
   - Test error modes, rate limiting, empty data

---

## Workstream 3: EXISTING_PARTIAL Gap Closure

**Priority:** P0 — maximizes value from already-implemented adapters
**Depends on:** Nothing (all are crawl-data-only improvements)

### 3.1 Rules with Adapters But Significant Remaining Gaps

These 7 EXISTING_PARTIAL rules have adapters but were classified during Phase 2 (not Phase 3/4A) and may need enhancement:

| Rule | Check | Primary Gap |
|------|-------|-------------|
| 2 | `sitemap_found` | Only checks existence; needs URL count validation, GSC submission status |
| 5 | `spider_trap_calendar` + `url_session_id` | Has 3 detection bodies; needs URL pattern library, GSC Crawl Stats |
| 13 | `missing_title` + `long_title` + `short_title` | Has detection; needs SERP truncation width check, pixel-width estimation |
| 23 | `response_time_ms` | Indirect CDN detection; needs Cache-Control header check, CDN provider detection |
| 25 | `mixed_content` + `https_redirect` | Has detection; needs SSL certificate validation (external dependency) |
| 40 | Fix Priority Checklist | Generates checklist; needs structured priority scoring |
| 66 | `font_size_legibility` | Has detection; needs contrast ratio check, WCAG compliance |

### 3.2 Approach Per Rule

For each rule: review current check function → identify enhancement → write additional tests → implement → update gap_description in CSV.

**Constraint:** NO rule can be upgraded to EXISTING_FULL unless ALL gaps are closed. Keep as EXISTING_PARTIAL if ANY heuristic/approximation remains.

---

## Workstream 4: GSC Provider Implementation

**Priority:** P0 — unblocks 9 rules
**Depends on:** GSC OAuth credentials

### 4.1 Implementation

1. **Create `audit_rules/providers/gsc_client.py`**
   - OAuth 2.0 authentication (service account or OAuth flow)
   - Search Analytics API: `searchanalytics.query()` with dimensions (page, query, country, device)
   - URL Inspection API: `urlInspection.index()` for index status, mobile usability, rich results
   - Sitemaps API: `sitemaps.list()` and `sitemaps.get()` for submitted/indexed counts
   - Rate limiting: GSC allows ~2,000 queries/day — implement caching and batching
   - Pagination: handle `rowLimit` (max 25,000 rows per request), `startRow` offset

2. **Create `audit_rules/providers/gsc_provider.py`**
   - `GSCProvider.provide(site_ctx, page_contexts)` → dict with:
     - `gsc_queries`: list of {query, clicks, impressions, ctr, position} per page
     - `gsc_index_status`: dict of URL → {indexed, mobile_usable, rich_results}
     - `gsc_sitemaps`: {submitted_count, indexed_count, last_submitted}
     - `gsc_manual_actions`: list of {action, date, status} (if API exposes)

3. **Write tests** — `tests/providers/test_gsc_provider.py`
   - Mock GSC API responses
   - Test auth failure, quota exceeded, empty property, no data

### 4.2 Rules Unlocked (9)

| Rule | Check Function | Data Needed |
|------|---------------|-------------|
| 23 | CDN detection enhancement | (existing adapter has partial check) |
| 25 | HTTPS validation enhancement | (existing adapter has partial check) |
| 35 | Conversion event tracking | GA4/GTM — requires GA4 provider too |
| 44 | Google-selected Canonical | GSC URL Inspection → `google_selected_canonical` |
| 52 | Keyword Cannibalization | GSC Queries + Semrush (dual provider) |
| 54 | Keyword→URL Mapping | GSC Queries + Semrush (dual provider) |
| 71 | GSC-specific checks | GSC Search Analytics |
| 72 | Manual Actions | GSC Manual Actions (may require manual review) |
| 73 | GSC Performance Trends | GSC Search Analytics time-series |

---

## Workstream 5: Semrush Provider Implementation

**Priority:** P0 — unblocks 4 rules
**Depends on:** Semrush API key (paid subscription)

### 5.1 Implementation

1. **Create `audit_rules/providers/semrush_client.py`**
   - REST API client with API key auth
   - Domain Analytics: `domain_ranks`, `domain_rank_keywords`, `backlinks`
   - Position Tracking: keyword positions for tracked domain

2. **Create `audit_rules/providers/semrush_provider.py`**

3. **Write tests** — `tests/providers/test_semrush_provider.py`

### 5.2 Rules Unlocked (4)

| Rule | Data Needed |
|------|-------------|
| 31 | Backlink Analytics (external link quality assessment) |
| 52 | Keyword data (with GSC) — cannibalization detection |
| 54 | Keyword→URL mapping (with GSC) |
| 65 | Position tracking, competitor comparison |

---

## Workstream 6: Server Log Provider Implementation

**Priority:** P1 — unblocks 3 rules
**Depends on:** Server log file access

### 6.1 Implementation

1. **Create `audit_rules/providers/server_log_provider.py`**
   - Log format auto-detection (Apache Combined, Nginx, JSON)
   - Bot user-agent classification (Googlebot, Bingbot, Yandex, etc.)
   - Status code aggregation, crawl frequency per URL/bot, response time distribution

2. **Write tests**

### 6.2 Rules Unlocked (3)

| Rule | Data Needed |
|------|-------------|
| 33 | Crawl frequency, status code distribution, bot breakdown |
| 34 | Crawl stats verification (cross-reference with GSC) |
| 64 | Crawl budget waste detection (high-frequency low-value URLs) |

---

## Workstream 7: GA4 Provider Implementation

**Priority:** P2 — unblocks 1 rule directly, enriches others
**Depends on:** GA4 Property ID + service account

### 7.1 Implementation

1. **Create `audit_rules/providers/ga4_provider.py`**
   - Google Analytics Data API (GA4)
   - Traffic source, engagement, conversion events

2. **Write tests**

### 7.2 Rules Unlocked (1 directly, enriches 35, 53, 54)

| Rule | Data Needed |
|------|-------------|
| 53 | Search intent matching — traffic + engagement by landing page |

---

## Workstream 8: WordPress Privileged Provider

**Priority:** P2 — unblocks 5 rules
**Depends on:** WordPress admin credentials, security review
**⚠️ HIGH SECURITY SENSITIVITY**

### 8.1 Implementation

1. **Create `audit_rules/providers/wordpress_privileged_provider.py`**
   - Plugin/theme inventory (active, inactive, versions)
   - User roles and counts
   - Core/plugin/theme update status
   - wp_options: siteurl, home, blog_public, permalink_structure
   - **READ-ONLY MODE REQUIRED** — no config changes via API

2. **Security requirements:**
   - `WP_READONLY_MODE=true` enforced at provider level
   - Rate limiting on admin-ajax.php / REST API
   - Credential in `.env`, never committed
   - Audit log of all accessed WP endpoints

3. **Write tests**

### 8.2 Rules Unlocked (5)

| Rule | Data Needed |
|------|-------------|
| 48 | Plugin/theme version check, known vulnerabilities |
| 68 | User role audit, unused accounts |
| 69 | WP core/plugin update status |
| 77 | WP-specific backlink data enrichment |
| 80 | WP-specific infrastructure monitoring enhancement |

---

## Workstream 9: Manual Review Workflow

**Priority:** P1 — unblocks 13 rules
**Depends on:** Nothing (can run in parallel with providers)

### 9.1 Rules Requiring Manual Review (13)

Rules: 36, 46, 53, 55, 56, 57, 66, 72, 73, 75, 76, 77, 80

These are classified `NEW_MANUAL` because they require human judgment (design quality, content strategy, competitive analysis) or privileged access not available via API.

### 9.2 Implementation Options

**Option A (Recommended): Structured Markdown Template**
- Generate `manual-review-<domain>.md` per audit
- Each of 13 rules gets a section with: description, what to look for, rating scale (Pass/Fail/Warning/Not Applicable), notes field
- Reviewer fills in findings, script parses completed template back into structured Findings

**Option B: Interactive CLI**
- `python -m audit_rules.manual_review` launches Q&A session
- Each rule prompts reviewer with contextual questions

**Option C: Hybrid**
- Template for async review + CLI for quick checks

### 9.3 Integration

- `ManualReviewProvider` produces a data dict from completed template
- `manual_review_checks.py` converts review data into structured Findings
- Together they satisfy the 13 NEW_MANUAL rules

---

## Workstream 10: NEW_EXTERNAL_DATA Rule Implementation

**Priority:** P1 — implement check functions AFTER corresponding provider is done
**Depends on:** Workstreams 4–8 (providers)

### 10.1 Approach Per Rule

For each of the 16 NEW_EXTERNAL_DATA rules:
1. Provider must be implemented and tested first
2. Write check function using provider data (via `data` dict)
3. Follow same pattern: `check_<rule>(rule, site_ctx, page_contexts, data) -> list[Finding]`
4. TDD: tests first, then implementation
5. Update CSV: `NEW_EXTERNAL_DATA` → `EXISTING_PARTIAL` (external dependency = cannot be FULL)

### 10.2 Rule Groupings by Provider

| Provider | Rules | Estimated Tests |
|----------|-------|-----------------|
| GSC | 35, 44, 52, 54, 71, 72, 73 | ~50-70 |
| Semrush | 31, 52, 54, 65, 75, 76, 77 | ~40-60 |
| Server Log | 33, 34, 64 | ~20-30 |
| GA4 | 35, 53 | ~15-20 |
| WordPress | 48, 68, 69, 77, 80 | ~30-40 |
| PSI | 21, 24, 62, 63 | ~25-35 |
| JS Rendering | 46, 48 | ~15-20 |

Note: some rules (35, 52, 54, 77) draw from multiple providers simultaneously.

---

## Workstream 11: Audit Score Computation

**Priority:** P2 — depends on all rules producing findings
**Depends on:** All 80 rules implemented

### 11.1 Design

```python
# audit_rules/scoring.py

class AuditScore:
    overall: float           # 0-100
    category_scores: dict    # category → score
    severity_distribution: dict  # Error/Warning/Info/Opportunity counts
    top_issues: list[Finding]    # Highest severity × highest confidence

def compute_score(findings: list[Finding], rules: list[RuleDefinition]) -> AuditScore:
    # Weighted by: severity × confidence × rule priority
    # Category weights defined in categories.py
```

### 11.2 Output Artifacts

- `score.json` — machine-readable score breakdown
- `score.md` — human-readable score report with recommendations
- Trend visualization (with Rule 74 snapshot diff)

---

## Workstream 12: Final Integration & Cleanup

**Priority:** P3 — polish and ship
**Depends on:** Workstreams 1–11 complete

### 12.1 Tasks

1. **Update `server.py` `_build_report()`** to include all new artifacts
2. **End-to-end integration test** — crawl → full 80-rule audit → all artifacts generated
3. **Performance audit** — ensure 80-rule audit on 500-page site completes in reasonable time
4. **CSV final state:** All 80 rows = EXISTING_FULL
5. **Remove all `EXISTING_PARTIAL` / `NEW_*` classifications**
6. **Final documentation update**
7. **Release tag:** `v3.0.0`

---

## Dependency Graph Summary

```
                    ┌─────────────┐
                    │  WS1: Rule  │
                    │  74 (4B)    │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
  ┌──────▼──────┐  ┌──────▼──────┐  ┌───────▼──────┐
  │ WS2: PSI    │  │ WS3: PARTIAL│  │ WS9: Manual  │
  │ Validation  │  │ Gap Closure │  │ Review       │
  └──────┬──────┘  └─────────────┘  └───────┬──────┘
         │                                   │
  ┌──────▼──────┐  ┌──────┐  ┌──────┐  ┌────▼────┐  ┌──────┐
  │ WS4: GSC    │  │ WS5: │  │ WS6: │  │ WS7: GA4│  │ WS8: │
  │ Provider    │  │Semrus│  │Server│  │ Provider│  │  WP  │
  └──────┬──────┘  │  h   │  │ Log  │  └────┬────┘  │Provid│
         │         └──┬───┘  └──┬───┘       │       └──┬───┘
         │            │         │           │          │
         └────────────┼─────────┼───────────┼──────────┘
                      │         │           │
              ┌───────▼─────────▼───────────▼──────────┐
              │        WS10: NEW_EXTERNAL_DATA         │
              │     16 rules → EXISTING_PARTIAL        │
              └───────────────────┬────────────────────┘
                                  │
                          ┌───────▼──────┐
                          │ WS11: Audit  │
                          │    Score     │
                          └───────┬──────┘
                                  │
                          ┌───────▼──────┐
                          │ WS12: Final  │
                          │ Integration  │
                          └──────────────┘
```

---

## Effort Estimates

| Workstream | Rules | Est. Hours | Parallel? |
|------------|-------|------------|-----------|
| WS1: Phase 4B (Rule 74) | 1 | 4–6 | Start first |
| WS2: PSI Validation | 0 (validates 8) | 2–3 | With WS1 |
| WS3: PARTIAL Gap Closure | 7 | 8–12 | With WS1/WS2 |
| WS4: GSC Provider | 9 | 8–12 | After WS2 |
| WS5: Semrush Provider | 4 | 6–10 | After WS2 |
| WS6: Server Log Provider | 3 | 4–6 | After WS2 |
| WS7: GA4 Provider | 1 (+2 enriched) | 4–6 | After WS2 |
| WS8: WP Privileged Provider | 5 | 6–10 | After WS2 |
| WS9: Manual Review | 13 | 6–10 | With providers |
| WS10: NEW_EXTERNAL_DATA Rules | 16 | 20–30 | After providers |
| WS11: Audit Score | 0 (cross-cutting) | 6–10 | After WS10 |
| WS12: Final Integration | 0 (cleanup) | 4–8 | After all |
| **TOTAL** | **33** | **78–113 hours** | |

---

## Suggested Execution Order

1. **Week 1:** WS1 (Rule 74) + WS2 (PSI Validation) + WS3 (PARTIAL gaps, in parallel)
2. **Week 2:** WS4 (GSC Provider, once credentials available) + WS9 (Manual Review, no deps)
3. **Week 3:** WS5 (Semrush) + WS6 (Server Logs) + WS7 (GA4) — parallel if API keys available
4. **Week 4:** WS8 (WP Privileged) + begin WS10 (implement rules as providers complete)
5. **Week 5:** Complete WS10 + WS11 (Audit Score)
6. **Week 6:** WS12 (Integration, end-to-end testing, documentation, release)

---

*End of REMAINING_IMPLEMENTATION_ROADMAP.md — proceed to FINAL_DEFINITION_OF_DONE.md next.*
