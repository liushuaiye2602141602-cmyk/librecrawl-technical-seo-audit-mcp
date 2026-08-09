# Blockers & Credentials — Codex Handoff

**Date:** 2026-08-09
**Related:** [CODEX_HANDOFF.md](CODEX_HANDOFF.md) | [CURRENT_SYSTEM_STATE.json](CURRENT_SYSTEM_STATE.json)

---

## 1. Credential Inventory

### 1.1 Present & Verified

| Credential | Status | Location | Notes |
|------------|--------|----------|-------|
| `PAGESPEED_API_KEY` | **PRESENT** | `.env` file | Key exists but has NOT been smoke-tested against live PSI API. Module: `audit_rules/providers/pagespeed_provider.py`. Client: `audit_rules/providers/psi_client.py`. |

### 1.2 Missing — Required for Completion

| Credential | Needed For | Rules Blocked | Setup Complexity |
|------------|------------|---------------|------------------|
| **GSC OAuth / API Key** | Google Search Console provider | 23, 25, 35, 44, 52, 54, 71, 72, 73 | HIGH — requires Google Cloud Console project, OAuth 2.0 setup, domain property verification |
| **Semrush API Key** | Semrush provider | 31, 52, 54, 65 | MEDIUM — paid subscription required, API key from account settings |
| **GA4 Property ID + OAuth** | Google Analytics 4 provider | 53 | HIGH — requires Google Cloud project, GA4 property setup, OAuth |
| **Server Log Access** | Server log provider | 33, 34, 64 | MEDIUM — needs log file path/URL, format parsing, rotation handling |
| **WordPress Admin Credentials** | WP privileged provider | 48, 68, 69, 77, 80 | HIGH — needs admin login, security considerations, rate limiting |

### 1.3 Credential Configuration Pattern

All credentials are loaded via environment variables or `.env` file. Feature flags in `server.py` / runner control which providers activate:

```python
# Feature flags (env vars with defaults)
MASTER_AUDIT_V3_ENABLED = os.getenv("MASTER_AUDIT_V3_ENABLED", "false")
MASTER_AUDIT_PSI_ENABLED = os.getenv("MASTER_AUDIT_PSI_ENABLED", "true")
PAGESPEED_API_KEY = os.getenv("PAGESPEED_API_KEY", "")
PSI_SAMPLE_LIMIT = int(os.getenv("PSI_SAMPLE_LIMIT", "20"))
PSI_STRATEGIES = os.getenv("PSI_STRATEGIES", "mobile")
```

New providers should follow this pattern.

---

## 2. Provider Blockers (Ordered by Dependency Chain)

### Blocker 1: PSI Smoke Test (P0 — unblocks nothing, but validates existing work)

**What:** Run PSI provider against a real site, verify it returns valid CrUX/Lighthouse data.
**Rules affected:** None directly (19, 20, 21, 22, 24, 61, 62, 63 already have adapters but use crawl data; PSI enriches them).
**Action:** Pick a test domain, run `psi_client.py` with the existing key, verify response parsing.

### Blocker 2: GSC Provider (P0 — unblocks 9 rules)

**What:** Implement `audit_rules/providers/gsc_provider.py` with GSC API client.
**Rules unlocked:** 23, 25, 35, 44, 52, 54, 71, 72, 73
**API scope needed:**
- Search Analytics (query impressions, clicks, CTR, position)
- Sitemaps (submitted vs indexed)
- URL Inspection (index status, mobile usability)
- Manual Actions (if API exposes — may be manual-only)

**Architecture:**
```
audit_rules/providers/
├── gsc_provider.py        # Provider class
├── gsc_client.py           # Low-level API client (auth, pagination, rate limiting)
└── gsc_schemas.py          # Response models / validation
```

### Blocker 3: Semrush Provider (P0 — unblocks 4 rules)

**What:** Implement `audit_rules/providers/semrush_provider.py`.
**Rules unlocked:** 31, 52, 54, 65
**API endpoints needed:**
- Domain Analytics (organic keywords, backlinks, traffic)
- Site Audit lite (if available at current tier)
- Position Tracking

### Blocker 4: Server Log Provider (P1 — unblocks 3 rules)

**What:** Implement `audit_rules/providers/server_log_provider.py`.
**Rules unlocked:** 33, 34, 64
**Data needed:**
- Log file ingestion (Apache/Nginx combined format, JSON)
- Log rotation handling
- Bot filtering (user-agent classification)
- Status code aggregation, crawl frequency analysis

### Blocker 5: GA4 Provider (P2 — unblocks 1 rule)

**What:** Implement `audit_rules/providers/ga4_provider.py`.
**Rules unlocked:** 53
**API scope:** Traffic source, engagement metrics, conversion events.

### Blocker 6: WordPress Privileged Provider (P2 — unblocks 5 rules)

**What:** Implement `audit_rules/providers/wordpress_privileged_provider.py`.
**Rules unlocked:** 48, 68, 69, 77, 80
**Data needed:**
- Plugin/theme inventory (via admin API or direct DB access)
- User roles and counts
- Core/plugin update status
- wp_options table for site settings

**⚠️ SECURITY WARNING:** This provider requires privileged access. Must support:
- Read-only mode (no config changes)
- Rate limiting on admin-ajax.php
- Credential rotation
- Audit log of all accessed endpoints

---

## 3. Technical Blockers

### Blocker 7: Rule 74 Snapshot Diff (P1 — unblocks 1 rule)

**What:** Implement `check_content_score_audit` with cross-audit snapshot comparison.
**Rules unlocked:** 74
**Architecture:** Needs snapshot storage (file-based JSON), diff engine, trend detection.
**Module:** `audit_rules/snapshot.py` (new) or `audit_rules/checks/snapshot_diff.py`

### Blocker 8: Manual Review Workflow (P1 — unblocks 13 rules)

**What:** Implement manual review UI/workflow for 13 NEW_MANUAL rules.
**Rules:** 36, 46, 55, 56, 57, 66, 72, 73, 75, 76, 77, 80, + partial-manual rules
**Architecture:** Could be CLI questionnaire, web form, or markdown template with review checkboxes.
**Artifact:** `docs/handoff/manual-review-template.md` or interactive CLI module.

### Blocker 9: Audit Score Computation (P2 — cross-cutting)

**What:** Implement weighted scoring across all 80 rules.
**Module:** `audit_rules/scoring.py` (new)
**Depends on:** All 80 rules producing findings with confidence scores.

---

## 4. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| GSC API quota limits | HIGH | Blocks 9 rules from live data | Implement caching, batch requests, quota monitoring |
| Semrush API tier too low | MEDIUM | Blocks 4 rules or returns limited data | Graceful degradation: flag "insufficient tier" in findings |
| PSI API key invalid/expired | LOW | Blocks PSI enrichment of 8 existing rules | Smoke test early; fall back to crawl-only data |
| WordPress admin credentials unavailable | MEDIUM | Blocks 5 rules | Implement "external data required" graceful failure |
| Server log format mismatch | MEDIUM | Blocks 3 rules | Support multiple formats (combined, JSON, custom) with configurable regex |
| Rate limiting on audited sites | LOW | Affects Rule 39 WP probes | Already mitigated: `WP_SECURITY_PROBES_ENABLED=false`, max 3 probes |
| CSV column shift regression | LOW | Breaks registry loading | The CSV parser is sensitive to unquoted commas — always quote multi-word fields |

---

## 5. README for Credential Setup

When credentials become available, add to `.env`:

```bash
# Google APIs
PAGESPEED_API_KEY=your_key_here
GSC_CLIENT_ID=your_client_id
GSC_CLIENT_SECRET=your_client_secret
GSC_REFRESH_TOKEN=your_refresh_token
GSC_SITE_URL=https://example.com

# Semrush
SEMRUSH_API_KEY=your_key_here

# GA4
GA4_PROPERTY_ID=123456789
GA4_CREDENTIALS_PATH=/path/to/service-account.json

# Server Logs
SERVER_LOG_PATH=/var/log/nginx/access.log
SERVER_LOG_FORMAT=combined

# WordPress
WP_SITE_URL=https://example.com
WP_APPLICATION_PASSWORD=xxxx:xxxx:xxxx:xxxx
WP_READONLY_MODE=true
```

---

*End of BLOCKERS_AND_CREDENTIALS.md — proceed to REMAINING_IMPLEMENTATION_ROADMAP.md next.*
