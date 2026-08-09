# Phase 1.1 — Legacy vs V3 Compatibility Matrix

**Date**: 2026-08-09 | **Version**: Phase 1.1 Final

---

## Executive Summary

All 18 EXISTING_FULL Master Audit rules were verified for compatibility between
the legacy audit pipeline (v2.x) and the new V3 adapter pipeline. Each rule was
evaluated on: data source parity, detection logic parity, finding parity, and
regression risk.

**Result**: 18/18 rules (100%) pass compatibility verification. Zero regressions.

---

## Compatibility Scores

| Score | Definition |
|:-----:|------------|
| ✅ **IDENTICAL** | Same data source, same logic, same output — zero risk |
| ⚠️ **EQUIVALENT** | Slightly different implementation path, same result — low risk |
| 🔄 **ENHANCED** | V3 adds detection capability while preserving legacy output — no regression |

---

## Per-Rule Compatibility Matrix

### Rule 1 — robots.txt Exists
| Dimension | Legacy | V3 Adapter | Verdict |
|-----------|--------|------------|:-------:|
| Data Source | `export_data["site_check"]["robots_txt"]` | `SiteContext.robots_txt` ← same source | ✅ |
| Detection Logic | Check `found=False` → Error | `_adapter_robots_txt()` — identical check | ✅ |
| Finding Fields | `type`, `url`, `description` | `Finding(url, detected, expected, evidence, detail, severity)` — superset | ⚠️ |
| Regression Risk | — | None — V3 preserves all legacy field semantics | ✅ |

**Score**: ⚠️ EQUIVALENT (richer finding model, same detection)

### Rule 3 — Page Noindex/Nofollow
| Dimension | Legacy | V3 Adapter | Verdict |
|-----------|--------|------------|:-------:|
| Data Source | `export_data["pages"][*]["robots"]` | `PageContext.robots` ← same source | ✅ |
| Detection Logic | `noindex` in robots → Error | `_adapter_noindex_nofollow()` — identical | ✅ |
| Regression Risk | — | None | ✅ |

**Score**: ✅ IDENTICAL

### Rule 4 — Crawl Errors (4xx/5xx)
| Dimension | Legacy | V3 Adapter | Verdict |
|-----------|--------|------------|:-------:|
| Data Source | `export_data["pages"][*]["status_code"]` | `PageContext.status_code` ← same source | ✅ |
| Detection Logic | `status_code >= 400` → Error | `_adapter_crawl_errors()` — identical | ✅ |
| Regression Risk | — | None | ✅ |

**Score**: ✅ IDENTICAL

### Rule 6 — Unified Domain + Protocol
| Dimension | Legacy | V3 Adapter | Verdict |
|-----------|--------|------------|:-------:|
| Data Source | `export_data["site_check"]["https_redirect"]` + `["www_redirect"]` | `SiteContext.https_redirects` + `SiteContext.www_redirect` ← same | ✅ |
| Detection Logic | Check redirect presence/validity | `_adapter_domain_protocol()` — identical | ✅ |
| Regression Risk | — | None | ✅ |

**Score**: ✅ IDENTICAL

### Rule 7 — Redirect Chain Audit
| Dimension | Legacy | V3 Adapter | Verdict |
|-----------|--------|------------|:-------:|
| Data Source | `export_data["pages"][*]` + redirect fields | `PageContext` redirect fields ← same | ✅ |
| Detection Logic | Chain length + loop detection | `_adapter_redirect_chains()` — identical | ✅ |
| Regression Risk | — | None | ✅ |

**Score**: ✅ IDENTICAL

### Rule 8 — Canonical Correctness
| Dimension | Legacy | V3 Adapter | Verdict |
|-----------|--------|------------|:-------:|
| Data Source | `export_data["pages"][*]["canonical_url"]` | `PageContext.canonical_url` ← same | ✅ |
| Detection Logic | Missing/self-ref/inconsistent canonicals → Error | `_adapter_canonical()` — identical | ✅ |
| Regression Risk | — | None | ✅ |

**Score**: ✅ IDENTICAL

### Rule 9 — Click Depth
| Dimension | Legacy | V3 Adapter | Verdict |
|-----------|--------|------------|:-------:|
| Data Source | `export_data["pages"][*]["depth"]` | `PageContext.depth` ← same | ✅ |
| Detection Logic | `depth > 3` → Warning | `_adapter_click_depth()` — identical threshold | ✅ |
| Regression Risk | — | None | ✅ |

**Score**: ✅ IDENTICAL

### Rule 11 — Internal Link Distribution
| Dimension | Legacy | V3 Adapter | Verdict |
|-----------|--------|------------|:-------:|
| Data Source | `export_data["pages"][*]` link counts + inbound | `PageContext.inbound_links_count` + `linked_from` ← same | ✅ |
| Detection Logic | Orphan/low-inlink detection | `_adapter_internal_links()` — identical | ✅ |
| Regression Risk | — | None | ✅ |

**Score**: ✅ IDENTICAL

### Rule 14 — Meta Description
| Dimension | Legacy | V3 Adapter | Verdict |
|-----------|--------|------------|:-------:|
| Data Source | `export_data["pages"][*]["meta_description"]` | `PageContext.meta_description` ← same | ✅ |
| Detection Logic | Missing/duplicate/short/long → Error/Warning | `_adapter_meta_description()` — identical thresholds | ✅ |
| Regression Risk | — | None | ✅ |

**Score**: ✅ IDENTICAL

### Rule 15 — H1 Heading Hierarchy
| Dimension | Legacy | V3 Adapter | Verdict |
|-----------|--------|------------|:-------:|
| Data Source | `export_data["pages"][*]["h1"]` | `PageContext.h1` ← same | ✅ |
| Detection Logic | Missing/duplicate/multiple H1 → Error | `_adapter_h1_headings()` — identical | ✅ |
| Regression Risk | — | None | ✅ |

**Score**: ✅ IDENTICAL

### Rule 26 — HSTS + Security Headers
| Dimension | Legacy | V3 Adapter | Verdict |
|-----------|--------|------------|:-------:|
| Data Source | `export_data["site_check"]` + response headers | `PageContext.response_headers` (lazy) ← same | ✅ |
| Detection Logic | Missing headers → Error | `_adapter_security_headers()` — identical | ✅ |
| Regression Risk | — | None | ✅ |

**Score**: ✅ IDENTICAL

### Rule 27 — Schema Type Coverage
| Dimension | Legacy | V3 Adapter | Verdict |
|-----------|--------|------------|:-------:|
| Data Source | `export_data["pages"][*]["json_ld"]` | `PageContext.json_ld_types` ← same source | ✅ |
| Detection Logic | Coverage ratio < threshold → Warning | `_adapter_schema_coverage()` — identical threshold | ✅ |
| Regression Risk | — | None | ✅ |

**Score**: ✅ IDENTICAL

### Rule 29 — Hreflang Basics
| Dimension | Legacy | V3 Adapter | Verdict |
|-----------|--------|------------|:-------:|
| Data Source | `export_data["pages"][*]["hreflang"]` | `PageContext.hreflang_tags` ← same | ✅ |
| Detection Logic | Missing x-default, self-ref issues → Warning | `_adapter_hreflang_basics()` — identical | ✅ |
| Regression Risk | — | None | ✅ |

**Score**: ✅ IDENTICAL

### Rule 30 — Broken Internal Links
| Dimension | Legacy | V3 Adapter | Verdict |
|-----------|--------|------------|:-------:|
| Data Source | `export_data["pages"][*]["status_code"]` + `links` | `PageContext.status_code` + `linked_from` ← same | ✅ |
| Detection Logic | 404/error pages with inbound links → Error | `_adapter_broken_links()` — identical | ✅ |
| Regression Risk | — | None | ✅ |

**Score**: ✅ IDENTICAL

### Rule 41 — Soft 404 Detection
| Dimension | Legacy | V3 Adapter | Verdict |
|-----------|--------|------------|:-------:|
| Data Source | `export_data["pages"][*]["word_count"]` + title | `PageContext.word_count` + title ← same | ✅ |
| Detection Logic | Thin content + 200 status → Warning | `_adapter_soft_404()` — identical | ✅ |
| Regression Risk | — | None | ✅ |

**Score**: ✅ IDENTICAL

### Rule 42 — Sitemap URL Indexability
| Dimension | Legacy | V3 Adapter | Verdict |
|-----------|--------|------------|:-------:|
| Data Source | `export_data["site_check"]["sitemap"]` | `SiteContext.sitemap` ← same | ✅ |
| Detection Logic | Sitemap URL count + indexability flags | `_adapter_sitemap_indexability()` — identical | ✅ |
| Regression Risk | — | None | ✅ |

**Score**: ✅ IDENTICAL

### Rule 45 — Orphan Pages
| Dimension | Legacy | V3 Adapter | Verdict |
|-----------|--------|------------|:-------:|
| Data Source | `export_data["pages"][*]["linked_from"]` | `PageContext.linked_from` ← same | ✅ |
| Detection Logic | `len(linked_from) == 0` and depth > 0 → Warning | `_adapter_orphan_pages()` — identical | ✅ |
| Regression Risk | — | None | ✅ |

**Score**: ✅ IDENTICAL

### Rule 58 — Hreflang Indexability
| Dimension | Legacy | V3 Adapter | Verdict |
|-----------|--------|------------|:-------:|
| Data Source | `export_data["pages"][*]["hreflang"]` | `PageContext.hreflang_tags` ← same | ✅ |
| Detection Logic | Hreflang target not indexable → Error | `_adapter_hreflang_indexability()` — identical | ✅ |
| Regression Risk | — | None | ✅ |

**Score**: ✅ IDENTICAL

---

## Summary Statistics

| Metric | Count |
|--------|:-----:|
| Rules verified | 18/18 (100%) |
| ✅ IDENTICAL | 17 |
| ⚠️ EQUIVALENT | 1 (Rule 1 — richer finding model) |
| 🔄 ENHANCED | 0 |
| ❌ REGRESSION | 0 |

---

## Cross-Cutting Verification

| Concern | Legacy | V3 | Compatible? |
|---------|--------|-----|:-----------:|
| Data source | Direct dict access | Context objects wrapping same dicts | ✅ Yes — same data |
| Lazy loading | N/A (all in memory) | Heavy fields lazy-loaded, auto-released | ✅ Yes — transparent |
| Finding format | Dict with legacy keys | `Finding` dataclass with `to_dict()` preserving all legacy keys | ✅ Yes — backward compat tested |
| Error handling | Legacy try/except per check | V3 adapter try/except + graceful degradation | ✅ Yes — equivalent or better |
| Network requests | 0 (all data pre-fetched) | 0 (all data from export) | ✅ Yes — zero new requests |
| Coverage reporting | None | 80-row coverage.csv (additive) | ✅ Yes — shadow only |

---

## Verified With

- 210 unit/integration tests (all passing)
- Programmatic CSV source-of-truth verification (18 EXISTING_FULL IDs → rule_ids → adapters)
- Production pipeline integration (feature flag ON/OFF behavior)
- Document source-of-truth sync (3 docs verified consistent with CSV)
