# Phase 3 — Existing PageSpeed Insights Architecture Audit

**Date:** 2026-08-09
**Audited:** `server.py`, `.env.example`, `install.sh`, `docker-compose.yml`, `docs/TOOLS.md`

---

## 1. Current PSI Tool Names

| MCP Tool | Scope | Location |
|----------|-------|----------|
| `librecrawl_pagespeed` | Single URL | `server.py:2349` |
| `librecrawl_pagespeed_audit` | Batch (max 25) | `server.py:2367` |
| `librecrawl_pagespeed_audit_all_crawl_pages` | Full crawl | `server.py:3467` |

---

## 2. Client / Request Layer

**File:** `server.py:2287-2298`

- Uses `httpx.get()` (sync) to `https://www.googleapis.com/pagespeedonline/v5/runPagespeed`
- Timeout: 30s
- Categories requested: `performance`, `seo`, `accessibility`, `best-practices`
- API key: `PAGESPEED_API_KEY` env var
- No dedicated client class — standalone function

---

## 3. Response Normalization

**File:** `server.py:2300-2346`

Field data (CrUX):
- Maps `loadingExperience.metrics` to dict with `{value, category}`
- Metrics: LCP, FID, CLS, INP, FCP, TTFB

Lab data (Lighthouse):
- `first-contentful-paint`, `largest-contentful-paint`, `total-blocking-time`
- `cumulative-layout-shift` (numericValue), `speed-index`, `interactive`

Top opportunities:
- Audits with `type == "opportunity"` and `overallSavingsMs > 200`
- Sorted by savings descending, capped at 5

Lighthouse scores: performance, seo, accessibility, best-practices (0-100)

**Normalization quality:** Good — clean, consistent output schema.

---

## 4. Mobile / Desktop Support

Yes — `strategy` parameter accepts `"mobile"` (default) or `"desktop"`.

---

## 5. Field Data (CrUX) Support

Yes — `loadingExperience.metrics` parsed for:
- `LARGEST_CONTENTFUL_PAINT_MS`
- `FIRST_INPUT_DELAY_MS`
- `CUMULATIVE_LAYOUT_SHIFT_SCORE`
- `INTERACTION_TO_NEXT_PAINT`
- `FIRST_CONTENTFUL_PAINT_MS`
- `EXPERIMENTAL_TIME_TO_FIRST_BYTE`

Returns `{value: percentile, category: "FAST"/"AVERAGE"/"SLOW"}`.

**Missing:** Does NOT distinguish URL-level vs Origin-level field data scope.
CrUX returns `loadingExperience.initial_url` and `originLoadingExperience` —
neither is exposed in the current normalization.

---

## 6. Lighthouse Audit Support

Yes — `lighthouseResult.audits` parsed. Scores from `categories`:
- `performance`, `seo`, `accessibility`, `best-practices`
- score × 100 for 0-100 scale

Opportunities extracted from audit `details.type == "opportunity"`.

**Missing:** Render-blocking resources, third-party scripts, font display,
image optimization, and layout-shift elements are available in Lighthouse
audits but NOT currently extracted by `_fetch_psi`.

---

## 7. Error Handling

Single catch-all: `except Exception as e: return {"error": str(e)}`.

Specific error cases NOT distinguished:
- API key missing → returns `{"error": "PAGESPEED_API_KEY not set."}`
- HTTP error → `{"error": str(e)}` (status code + body)
- Timeout → `{"error": str(e)}`
- JSON parse error → `{"error": str(e)}`
- No field data → returns empty `field_data_cwv: {}`
- Lighthouse runtime error → caught by general exception handler

---

## 8. Retry Behavior

**None.** Single attempt per URL. No exponential backoff. No 429 handling.

---

## 9. Caching Behavior

**None.** Every call fetches live from PSI API. No session-level cache.
Same URL + same strategy = new API call each time.

---

## 10. API Key Handling

- Env var: `PAGESPEED_API_KEY`
- Default: empty string
- Checked once at function entry: `if not PSI_API_KEY: return {"error": ...}`
- Set in `.env.example`, `install.sh` (prompted), `docker-compose.yml` (passthrough)

---

## 11. Batch / Audit Implementation

| Function | Max URLs | Rate | Returns |
|----------|----------|------|---------|
| `librecrawl_pagespeed_audit` | 25 (hardcoded cap) | 1.1s delay | Summary + results list |
| `librecrawl_pagespeed_audit_all_crawl_pages` | No cap (limit param) | Configurable delay | Results + error list |

Both do serial fetch — no parallelism.

---

## 12. Existing Tests

**None.** No test file references `_fetch_psi` or any PSI tool.

---

## 13. Existing PSI Integration with Audit Pipeline

**None.** PSI tools are standalone MCP tools. They are NOT connected to:
- Rule Registry
- CompatibilityHarness
- RuleRunner
- CoverageManager
- audit artifacts (coverage.csv, master-audit-tasks.csv)

Phase 3 is the FIRST integration of PSI data into the V3 audit pipeline.

---

## Conclusion: WRAP

`_fetch_psi()` is a clean, well-structured function. Phase 3 should:

1. **WRAP** — create `PageSpeedDataProvider` that calls `_fetch_psi()` internally
2. **DO NOT re-implement** — no second PSI HTTP client
3. **EXTEND normalization** — add `PerformanceSnapshot` model with:
   - URL vs Origin field data scope
   - Render-blocking resources
   - Third-party script diagnostics
   - Image optimization opportunities
   - Font display / CLS diagnostics
4. **ADD caching** — session-level in-memory cache (URL + strategy key)
5. **ADD sampling** — template-aware representative URL selection
6. **ADD failure semantics** — unavailable / partial / error states
7. **KEEP MCP tools unchanged** — `librecrawl_pagespeed*` signatures intact

**No replacement needed.** The existing PSI client is adequate.
