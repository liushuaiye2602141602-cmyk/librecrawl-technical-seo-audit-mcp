# Codex Start Prompt — Master SEO Audit System

**INSTRUCTIONS:** Copy everything below the `---` separator and paste it as your first message to Codex (or any capable AI coding agent). This prompt is designed to be self-contained — Codex does not need the prior conversation history to understand the task.

---

```
You are taking over the Master SEO Audit System project from a previous developer who completed Phases 1–4A. Your task is to complete the ENTIRE remaining system — all 80 rules, all providers, all artifacts, audit score, and final integration.

## BEFORE YOU DO ANYTHING ELSE

Read these files in order. They contain everything you need to know:

1. `docs/handoff/CODEX_HANDOFF.md` — architecture overview, constraints, key patterns
2. `docs/handoff/BLOCKERS_AND_CREDENTIALS.md` — credential status, blockers
3. `docs/handoff/CURRENT_RULE_MATRIX.csv` — exact state of all 80 rules (80 data rows)
4. `docs/handoff/CURRENT_SYSTEM_STATE.json` — machine-readable state snapshot
5. `docs/handoff/REMAINING_IMPLEMENTATION_ROADMAP.md` — ordered 12-workstream plan
6. `docs/handoff/FINAL_DEFINITION_OF_DONE.md` — 37 conditions for completion

Also read these supporting documents:
7. `docs/audit/PHASE4A_COMPLETION_REPORT.md` — what Phase 4A delivered
8. `docs/audit/PHASE4A_STATUS_MIGRATION.md` — per-rule classification rationale

## VERIFY YOUR ENVIRONMENT

```bash
cd <project_root>/librecrawl-technical-seo-audit-mcp
pytest tests/ -q
# Should show 457 passed, 0 failed
```

## WHAT YOU ARE BUILDING

A Master Technical SEO Audit System that evaluates 80 SEO rules against crawled website data.

**Current state (commit 328760f):**
- 47/80 rules have working check functions
- 2/6 data providers implemented (LibreCrawl + PSI)
- 457 tests passing
- 33 rules still need implementation
- 4 providers still need to be built
- Manual review workflow not started
- Audit score not implemented
- Snapshot diff (Rule 74) not implemented

**Target state:**
- 80/80 rules fully implemented (all EXISTING_FULL)
- 7/7 providers implemented and live-validated
- >=1,200 tests passing
- All 37 conditions in FINAL_DEFINITION_OF_DONE.md satisfied
- CSV: 80 rows, all impl_status=EXISTING_FULL, no None check names
- Audit score computed per audit
- Manual review workflow operational
- Snapshot diff (Rule 74) working

## NON-NEGOTIABLE CONSTRAINTS

These cannot be violated. Period.

1. **ZERO additional HTTP requests in check functions.** All crawl-data-only rules use existing `page_contexts`/`site_ctx` data.
2. **Crawl once → normalize once → evaluate many.** Never N rules × N pages × HTTP refetch.
3. **Provider separation.** External API calls go through Provider classes, never in check functions.
4. **Check function pattern:**
   ```python
   def check_<rule>(rule: RuleDefinition, site_ctx: SiteContext,
                     page_contexts: list[PageContext], data: dict) -> list[Finding]:
   ```
5. **Finding factory:** Use `_mk(rule, severity=Severity.Warning, confidence=0.75, ...)` with explicit Severity enum (Error/Warning/Info/Opportunity).
6. **Confidence:** Float 0.0–1.0, not HIGH/MEDIUM/LOW enum.
7. **CSV is source of truth.** Any classification change must update `master_audit_mapping.csv` AND all affected test files.
8. **Having an adapter ≠ EXISTING_FULL.** Keep EXISTING_PARTIAL if heuristic/approximation gaps remain.
9. **TDD required.** Write tests first, then implementation.
10. **Full regression after every change.** `pytest tests/ -q` must pass.
11. **No destructive operations.** No POST/PUT/DELETE to audited sites.
12. **Rule 39:** WP probes default off. Max 3 GET/HEAD. No POST.
13. **Rule 67:** No DNS scanning, no brute-force subdomain enumeration.
14. **Lazy imports** via try/except in `checks/__init__.py`.
15. **Never merge/rebase** without explicit instruction.
16. **Checkpoint commits between phases.**

## KEY ARCHITECTURE FACTS

### Three-layer classification
```
impl_status (CSV) ≠ adapter_exists (code) ≠ execution_status (runtime)
```

### Adapter registration (add new phases here)
```python
# In audit_rules/adapters.py
def _load_phaseX_checks() -> dict[str, Callable]:
    from audit_rules.checks import get_check
    return {"rule_id": get_check("check_name"), ...}

# In __post_init__:
self._adapters.update(_load_phaseX_checks())
```

### Key files
- `audit_rules/runner.py` — MasterAuditRunner orchestrator
- `audit_rules/registry.py` — loads checklist + mapping CSVs
- `audit_rules/adapters.py` — maps rule_id → check function
- `audit_rules/models.py` — RuleDefinition, Finding, PageContext, SiteContext
- `audit_rules/checks/__init__.py` — lazy imports, `get_check()` accessor
- `audit_rules/checks/phase4a_rules.py` — reference implementation (~700 lines, 8 checks)
- `audit_rules/providers/` — data providers (LibreCrawl, PSI, + 5 more to build)
- `audit_specs/master_audit_mapping.csv` — SOURCE OF TRUTH (15 columns, 80 rows)
- `audit_specs/technical_seo_master_checklist_80.csv` — rule definitions

### Provider pattern
```python
class SomeProvider(BaseProvider):
    def provide(self, site_ctx: SiteContext, page_contexts: list[PageContext]) -> dict:
        # Returns data dict passed to check functions via `data` param
```

## RECOMMENDED EXECUTION ORDER

### Phase 4B: Rule 74 Snapshot Diff (do this first)
1. Design snapshot JSON format
2. Create `audit_rules/snapshot.py` (save/load/diff)
3. Create `audit_rules/checks/snapshot_diff.py` (`check_content_score_audit`)
4. Register adapter in `adapters.py`
5. Write ~15-20 tests in `tests/phase4b/test_snapshot_diff.py`
6. Update CSV: Rule 74 → EXISTING_PARTIAL

### Provider Workstreams (can run in parallel once credentials are available)
- GSC Provider → unblocks 9 rules
- Semrush Provider → unblocks 4 rules
- Server Log Provider → unblocks 3 rules
- GA4 Provider → unblocks 1 rule (+ enriches others)
- WordPress Privileged Provider → unblocks 5 rules (HIGH SECURITY — read-only mode)

### Parallel work (no credential dependencies)
- EXISTING_PARTIAL gap closure (7 rules with adapters needing enhancement)
- Manual Review Workflow (13 NEW_MANUAL rules)
- PSI live validation

### After providers complete
- Implement 16 NEW_EXTERNAL_DATA check functions
- Audit Score computation
- Final integration, end-to-end testing, documentation

## HOW TO ADD A NEW CHECK (reference pattern from Phase 4A)

1. Create check module: `audit_rules/checks/<module>.py`
2. Implement `check_<rule>(rule, site_ctx, page_contexts, data) -> list[Finding]`
3. Add lazy import to `audit_rules/checks/__init__.py`:
   ```python
   _MODULES["<module>"] = {
       "module": "audit_rules.checks.<module>",
       "functions": ["check_foo", "check_bar"],
   }
   ```
4. Add adapter loader to `audit_rules/adapters.py`:
   ```python
   def _load_phaseX_checks():
       from audit_rules.checks import get_check
       return {"rule_id": get_check("check_foo"), ...}
   ```
5. Write TDD tests: `tests/phaseX/test_<module>.py`
6. Update CSV: `impl_status`, `current_check_name`, `current_module`, `gap_description`
7. Update ALL affected test files (6+ files reference counts/sets)
8. Run full regression: `pytest tests/ -q`
9. Commit checkpoint

## CRITICAL PITFALLS TO AVOID

1. **CSV column shifts:** Always quote multi-word gap_description fields in CSV. An unquoted comma shifts all subsequent columns right.
2. **Case sensitivity:** Finding severity is title case: `Error`/`Warning`/`Info`/`Opportunity`. Test assertions must match.
3. **Test count updates:** When you add rules, update ALL test files that reference counts: `test_registry_integrity.py`, `test_master_id_adapter_binding.py`, `test_existing_full_compatibility.py`, `test_phase2_partial_rule_set.py`, `test_phase3_checks.py`, `test_phase4a/test_new_auto_rule_set.py`.
4. **Adapter count:** Currently 47. Must increment with each new rule implemented.
5. **EXISTING_PARTIAL set in `test_phase2_partial_rule_set.py`:** The PARTIAL_RULE_IDS set must stay in sync with CSV.
6. **Never skip the false-positive gate test.** Every check needs at least one test proving clean pages produce 0 findings.

## CREDENTIAL STATUS

- PAGESPEED_API_KEY: PRESENT in .env (not smoke-tested)
- GSC: NOT AVAILABLE (needs Google Cloud OAuth setup)
- Semrush: NOT AVAILABLE (needs paid subscription API key)
- GA4: NOT AVAILABLE (needs property + service account)
- Server Logs: NOT AVAILABLE (needs log file access)
- WordPress Admin: NOT AVAILABLE (needs admin credentials)

## QUESTIONS TO ASK THE USER BEFORE STARTING

1. "Do you have GSC OAuth credentials, or should I build the provider with mock data first?"
2. "Do you have a Semrush API key, or should I build the provider with mock data?"
3. "Should I prioritize the stateless Phase 4B (Rule 74 snapshot diff) first since it has no credential dependencies?"
4. "Do you want me to create a new git branch for this work, or continue on `feat/master-audit-foundation`?"
5. "What is the target timeline for completion?"

## IMMEDIATE NEXT ACTION

After reading the handoff documents and running `pytest tests/ -q` to verify 457 tests pass, your first implementation task should be:

**Phase 4B — Rule 74 (Snapshot Diff)**
This is the 1 remaining NEW_AUTO rule. It has no credential dependencies, no external API needs, and is fully specifiable in code. Implement it following the pattern in `audit_rules/checks/phase4a_rules.py`.

Then proceed through the workstreams in priority order (P0 → P1 → P2) as documented in `REMAINING_IMPLEMENTATION_ROADMAP.md`.

Good luck.
```
---

## How To Use This Prompt

1. Open a new session with Codex (or any capable AI coding agent)
2. Copy the entire code block above (everything between the ``` markers)
3. Paste it as your first message
4. Codex will read the handoff documents and begin implementation

**Important:** This prompt references 6 handoff files. Make sure all 6 files exist in `docs/handoff/` before handing off. The prompt assumes Codex can read files from the project directory.

---

*End of CODEX_START_PROMPT.md — handoff package complete.*
