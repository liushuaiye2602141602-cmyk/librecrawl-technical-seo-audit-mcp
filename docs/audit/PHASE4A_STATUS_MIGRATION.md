# Phase 4A — Rule Status Migration

**Date:** 2026-08-09
**Phase:** 4A — NEW_AUTO Stateless SEO Rules

---

## Migration Summary

All 8 Phase 4A rules migrated from `NEW_AUTO` → `EXISTING_PARTIAL`.

| Rule ID | Rule Name | CSV Rule ID | Check Function | New Module | Remaining Gaps (why PARTIAL) |
|---------|-----------|-------------|----------------|------------|------------------------------|
| 18 | Tags/Archives/Search Indexability | `tag_archive_search_indexability` | `check_archive_search_indexability` | `checks/phase4a_rules.py` | URL pattern heuristics only (not CMS-specific); user policy configuration still manual |
| 32 | Image/Video Sitemap | `media_sitemap` | `check_media_sitemap` | `checks/phase4a_rules.py` | Raw text namespace detection (not full XML parsing); image count threshold heuristic |
| 39 | WordPress XML-RPC/REST API Exposure | `xmlrpc_rest_api_exposure` | `check_wordpress_api_exposure` | `checks/phase4a_rules.py` | Crawl-only detection (no active HTTP probes by default); wp-login.php rate limiting not checked |
| 43 | Sitemap lastmod Accuracy | `sitemap_lastmod_accuracy` | `check_sitemap_lastmod` | `checks/phase4a_rules.py` | No cross-audit historical comparison; sitemap data availability depends on crawl config |
| 47 | Crawlable <a href> Links | `crawlable_a_href_links` | `check_crawlable_links` | `checks/phase4a_rules.py` | Requires raw HTML in export (not always available); regex heuristics miss SPA routers; modal/button vs navigation distinction |
| 51 | Internal Links → Redirect URLs | `internal_links_to_redirects` | `check_internal_redirect_links` | `checks/phase4a_rules.py` | Only detects targets already in crawl; no multi-hop redirect chain analysis |
| 60 | Multi-language Canonical | `multilingual_canonical` | `check_multilang_canonical` | `checks/phase4a_rules.py` | URL path language detection is heuristic (/es/ could be product category); no IP/UA redirect detection; no hreflang vs canonical conflict check |
| 67 | Staging/Dev Indexability | `staging_site_indexed` | `check_staging_indexability` | `checks/phase4a_rules.py` | Cannot prove staging absence; no DNS/subdomain scanning (by design); password protection detection limited to noindex |

## Classification Count Changes

```
                       Before      After
─────────────────────────────────────────
EXISTING_FULL:            18          18
EXISTING_PARTIAL:         24  →       32   (+8 Phase 4A)
NEW_AUTO:                  9  →        1   (Rule 74 only — Phase 4B)
NEW_EXTERNAL_DATA:        16          16
NEW_MANUAL:               13          13
─────────────────────────────────────────
TOTAL:                    80          80
```

## Adapter Registration

- **Before:** 39 adapters (18 P1 + 13 P2 + 8 P3)
- **After:** 47 adapters (18 P1 + 13 P2 + 8 P3 + 8 P4A)

## Decision Rationale — Why EXISTING_PARTIAL, not EXISTING_FULL

Per user directive Step 2:
> "实现了代码 不等于 必须升级 EXISTING_FULL。如果仍需要用户策略/额外输入/未发现的 staging URL/WordPress Admin/JS rendering/其他外部数据才能完整判断，则必须保持 PARTIAL。禁止为了减少 NEW_AUTO 数量强行 FULL。"

All 8 rules have remaining gaps in one or more areas:
1. **Heuristic dependence** (Rules 18, 60): URL pattern matching is approximate
2. **Data availability not guaranteed** (Rules 43, 47): sitemap data, raw HTML
3. **No active probing** (Rules 39, 67): crawl-only detection
4. **Incomplete crawl coverage** (Rule 51): only targets already in crawl
5. **Optional enhancement** (Rule 32): media sitemaps are not required

## Tests

- 72 Phase 4A-specific TDD tests pass (positive detection, edge cases, false-positive gates)
- 8 NEW_AUTO rule set tests updated for post-migration status
- Full suite: 457 tests pass (0 failures)
