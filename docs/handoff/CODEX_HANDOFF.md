# Codex Handoff — Master SEO Audit System

**Handoff Date:** 2026-08-09
**Git Commit:** `328760f` — `feat: checkpoint master audit phases 3 through 4a`
**Branch:** `feat/master-audit-foundation`
**Tests:** 457 passed, 0 failed
**Handoff Type:** COMPLETE PROJECT HANDOFF — build the ENTIRE remaining system

---

## 1. What This Project Is

A **Master Technical SEO Audit System** that evaluates 80 SEO rules against crawled website data. It ingests LibreCrawl exports, runs 47 implemented check functions against page-level and site-level data, and produces structured findings (CSV reports, JSON artifacts).

**Core architecture:** crawl once → normalize once → evaluate many rules (NOT N rules × N pages × HTTP refetch).

**Primary entry point:** `audit_rules/runner.py` — `MasterAuditRunner` orchestrates the full pipeline.

---

## 2. Current State Summary

| Metric | Value |
|--------|-------|
| Total rules | 80 (IDs 1..80) |
| Rules with working adapters | 47 (18 FULL + 32 PARTIAL + 8 Phase 3 + 8 Phase 4A) |
| Rules NOT implemented | 33 |
| Tests | 457 passing |
| Providers implemented | LibreCrawl (full), PageSpeed Insights (implemented, not smoke-tested) |
| Providers NOT started | GSC, Semrush, GA4, Server Logs, WordPress Privileged |

### Classification Breakdown

| Classification | Count | Meaning |
|----------------|-------|---------|
| EXISTING_FULL | 18 | Fully implemented, production-ready |
| EXISTING_PARTIAL | 32 | Partially implemented, has adapter, gaps remain |
| NEW_AUTO | 1 | Rule 74 only — can be automated, deferred to Phase 4B |
| NEW_EXTERNAL_DATA | 16 | Needs external API/data provider first |
| NEW_MANUAL | 13 | Requires manual review workflow |
| **TOTAL** | **80** | |

### Implementation Phases Completed

| Phase | Rules | Count | Description |
|-------|-------|-------|-------------|
| Phase 1 | 1,3,4,6,7,8,9,11,14,15,26,27,29,30,41,42,45,58 | 18 | EXISTING_FULL — hardcoded adapters |
| Phase 2 | 10,12,16,17,28,37,38,49,50,59,70,78,79 | 13 | EXISTING_PARTIAL — lazy-loaded checks |
| Phase 3 | 19,20,21,22,24,61,62,63 | 8 | Performance/PSI checks |
| Phase 4A | 18,32,39,43,47,51,60,67 | 8 | NEW_AUTO → EXISTING_PARTIAL stateless rules |

---

## 3. Key Architecture

### 3.1 Three-Layer Classification

```
impl_status (CSV) ≠ adapter_exists (code) ≠ execution_status (runtime)
```

- `impl_status` — declared in `audit_specs/master_audit_mapping.csv` (source of truth)
- `adapter_exists` — whether a check function is registered in `CompatibilityHarness._adapters`
- `execution_status` — per-audit: did the rule actually produce findings?

### 3.2 Check Function Pattern

```python
def check_<rule>(rule: RuleDefinition, site_ctx: SiteContext,
                  page_contexts: list[PageContext], data: dict) -> list[Finding]:
```

- `rule` — RuleDefinition from registry (has default severity, confidence)
- `site_ctx` — SiteContext (domain, crawl metadata, aggregated data)
- `page_contexts` — list of PageContext (per-page crawl data)
- `data` — arbitrary dict for cross-rule shared data
- Returns `list[Finding]` — empty list if no issues found

### 3.3 Finding Factory

```python
from audit_rules.checks.phase4a_rules import _mk
finding = _mk(rule, severity=Severity.Warning, confidence=0.75,
              page_url=url, detected_value=val, description="...")
```

Always use explicit `Severity` enum (title case: `Error`/`Warning`/`Info`/`Opportunity`). Confidence is float-based (1.0–0.4), no HIGH/MEDIUM/LOW enum.

### 3.4 Adapter Registration (Lazy Loading)

```python
def _load_phase4a_checks() -> dict[str, Callable]:
    # In audit_rules/adapters.py
    from audit_rules.checks import get_check
    return {"rule_id": get_check("check_function_name"), ...}
```

Merged into `CompatibilityHarness._adapters` in `__post_init__`. Each phase gets its own loader function.

### 3.5 Provider Pattern

```python
class SomeProvider(BaseProvider):
    def provide(self, site_ctx: SiteContext, page_contexts: list[PageContext]) -> dict:
        # Returns data dict that gets passed to check functions via `data` param
```

Registered in `audit_rules/providers/`. LibreCrawl and PSI are implemented.

### 3.6 Key Files

| File | Purpose |
|------|---------|
| `audit_rules/runner.py` | Main orchestrator — `MasterAuditRunner` |
| `audit_rules/registry.py` | Rule registry — loads checklist + mapping CSVs |
| `audit_rules/adapters.py` | Compatibility harness — maps rule_id → check function |
| `audit_rules/models.py` | Data models — RuleDefinition, Finding, PageContext, SiteContext |
| `audit_rules/context.py` | Context builders |
| `audit_rules/coverage.py` | Coverage analysis |
| `audit_rules/writer.py` | Output writers (CSV, JSON) |
| `audit_rules/integration.py` | Integration layer |
| `audit_rules/checks/__init__.py` | Lazy imports, `get_check()` accessor |
| `audit_rules/checks/phase4a_rules.py` | Phase 4A check functions (~700 lines) |
| `audit_rules/checks/performance.py` | Phase 3 performance checks |
| `audit_rules/checks/performance_csv.py` | Phase 3 CSV export checks |
| `audit_rules/providers/librecrawl_provider.py` | LibreCrawl data provider |
| `audit_rules/providers/pagespeed_provider.py` | PSI provider (implemented, not smoke-tested) |
| `audit_rules/providers/psi_client.py` | Low-level PSI API client |
| `audit_rules/providers/performance_snapshot.py` | Performance snapshot provider |
| `audit_specs/master_audit_mapping.csv` | **SOURCE OF TRUTH** — 80-row CSV with impl_status |
| `audit_specs/technical_seo_master_checklist_80.csv` | 80-rule checklist definitions |
| `server.py` | Legacy server — `_build_report()` function |

---

## 4. Non-Negotiable Constraints

### 4.1 Architecture Constraints

1. **ZERO additional HTTP requests per check function.** All crawl-data-only rules must use existing `page_contexts`/`site_ctx` data. No `requests.get()` inside a check function.
2. **Crawl once → normalize once → evaluate many.** Never N rules × N pages × HTTP refetch.
3. **Stateless checks.** Each rule operates on a single audit's data. No cross-audit state, no historical comparison, no persistent storage (except for Phase 4B snapshot diff).
4. **Lazy loading.** New check modules must use try/except lazy imports in `checks/__init__.py`. Never import heavy dependencies at module level.
5. **Provider separation.** External API calls go through Provider classes, never directly in check functions.

### 4.2 Classification Constraints

6. **CSV is source of truth.** `master_audit_mapping.csv` `impl_status` column defines classification. Code registration (`adapter_exists`) is separate.
7. **Having an adapter ≠ EXISTING_FULL.** Rules with remaining gaps (heuristic detection, missing external data, user policy needed) must stay `EXISTING_PARTIAL`.
8. **Never downgrade** EXISTING_FULL → EXISTING_PARTIAL without explicit justification.
9. **Every classification change must be reflected in CSV AND all affected test files.**

### 4.3 Code Constraints

10. **Check function naming:** `check_<snake_case_name>` matching CSV `check` column where possible.
11. **Finding severity:** Explicit `Severity` enum, never strings. Title case: `Error`/`Warning`/`Info`/`Opportunity`.
12. **Confidence:** Float 0.0–1.0. Heuristic detections get lower confidence (0.6–0.75). Hard evidence gets 1.0.
13. **`_mk()` factory:** Use the factory pattern from `phase4a_rules.py` for creating Findings from RuleDefinition defaults.
14. **False-positive gates:** Every check must have tests proving clean/normal sites don't trigger spurious findings.

### 4.4 Safety Constraints

15. **Rule 39 (WordPress API):** `WP_SECURITY_PROBES_ENABLED=false` by default. Max 3 GET/HEAD per host. Never POST.
16. **Rule 67 (Staging):** No DNS scanning, no brute-force subdomain enumeration, no hostname guessing.
17. **No destructive operations.** No POST/PUT/DELETE to audited sites. No automated wp-login.php probing.

### 4.5 Process Constraints

18. **TDD required.** Write tests first, then implementation. Each check needs positive detection + false-positive gate + edge case tests.
19. **Full regression after every change.** `pytest tests/ -q` must pass before commit.
20. **No merge/rebase without explicit user instruction.**
21. **Checkpoint commits between phases.** Never lose working state.

---

## 5. File Map — Handoff Package

```
docs/handoff/
├── CODEX_HANDOFF.md                       ← YOU ARE HERE (main entry point)
├── CURRENT_SYSTEM_STATE.json              ← Machine-readable state snapshot
├── CURRENT_RULE_MATRIX.csv                ← 80-rule matrix with workstream assignments
├── BLOCKERS_AND_CREDENTIALS.md            ← Credential status, blockers, risk assessment
├── REMAINING_IMPLEMENTATION_ROADMAP.md    ← Detailed implementation plan for all remaining work
├── FINAL_DEFINITION_OF_DONE.md            ← 35 completion conditions
└── CODEX_START_PROMPT.md                  ← Copy-paste prompt to launch Codex
```

**Supporting documents** (already existing, not in handoff/):
```
docs/audit/
├── PHASE4A_COMPLETION_REPORT.md           ← Phase 4A completion details
└── PHASE4A_STATUS_MIGRATION.md            ← Per-rule migration rationale
```

---

## 6. Quick-Start for Codex

1. **Read this file first** to understand architecture and constraints.
2. **Read `BLOCKERS_AND_CREDENTIALS.md`** to know what credentials exist.
3. **Read `CURRENT_RULE_MATRIX.csv`** to see the exact state of all 80 rules.
4. **Read `REMAINING_IMPLEMENTATION_ROADMAP.md`** for the ordered work plan.
5. **Copy-paste `CODEX_START_PROMPT.md`** to launch.

### Minimum Viable Verification

```bash
cd librecrawl-technical-seo-audit-mcp
pytest tests/ -q    # Should show 457 passed
```

---

## 7. What "Done" Looks Like

All 35 conditions in [FINAL_DEFINITION_OF_DONE.md](FINAL_DEFINITION_OF_DONE.md) satisfied:
- All 80 rules have adapters AND produce meaningful findings
- All 6 providers implemented and live-validated
- 80-rule CSV: 80 EXISTING_FULL, 0 everything else
- ≥1,200 tests passing
- Manual review workflow operational
- Audit Score computed
- Snapshot diff (Rule 74) working

---

## 8. Key Contacts / Context

- **Project owner:** The user who commissioned this handoff
- **Prior developer:** Claude (Anthropic) — implemented Phases 1–4A
- **No team members** — this is a solo project being handed off
- **No Jira/Linear tickets** — all planning is in these handoff documents
- **No CI/CD pipeline** — tests run locally via `pytest`

---

*End of CODEX_HANDOFF.md — proceed to BLOCKERS_AND_CREDENTIALS.md next.*
