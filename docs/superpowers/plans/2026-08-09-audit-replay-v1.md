# Audit Replay V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a credential-free, versioned, validated replay artifact that can rerun the current crawl-backed Master Audit pipeline offline and is packaged only for V3-enabled audits.

**Architecture:** A focused `audit_rules/replay.py` owns schema, sanitization, deterministic gzip serialization, validation, loading, provider normalization, and pipeline input reconstruction. `runner.py` supplies the final post-sitemap-fill inputs, writes and reload-validates the artifact after the V3 pipeline, registers only valid output, and reuses existing partial-artifact failure events.

**Tech Stack:** Python 3.12, dataclasses/JSON/gzip/hashlib/pathlib, pytest, existing RuleRunner/runner/state/ZIP pipeline.

## Global Constraints

- Artifact name is `<domain>-<timestamp>.audit-replay-v1.json.gz`; schema version is `1.0` and artifact type is `audit_replay`.
- Preserve all current normalized crawl-layer inputs needed by adapters, rules, contexts, snapshots, tasks, score, reports, and packaging without refetching.
- Response headers use a fixed safe allowlist; authorization, cookie, API-key, bearer, session, token, and credential-like values never persist.
- Provider evidence is normalized, sanitized, credential-free, and real; unavailable sources are explicitly pending/unavailable and mock evidence is forbidden.
- Serialization is stable by URL/key order; the external file SHA-256 is not embedded in the artifact.
- Write, reload, and validate before registration; page parity failure is `REPLAY_ARTIFACT_INCOMPLETE` and blocks acceptance.
- Feature flag off preserves legacy behavior. Do not add rules/providers or refactor unrelated code.
- Follow failing test -> minimal implementation -> related tests -> full regression.
- Do not force-push, rebase, merge PR #1, delete branches, or tag a release.

---

### Task 1: Schema, sanitization, deterministic writer, loader, and integrity validation

**Files:**
- Create: `audit_rules/replay.py`
- Create: `tests/phase12/test_replay_roundtrip.py`
- Create: `tests/phase12/test_replay_sensitive_fields.py`
- Create: `tests/phase12/test_replay_integrity.py`

**Interfaces:**
- Produces: `sanitize_response_headers(headers: dict | None) -> dict[str, str]`
- Produces: `build_replay_document(...) -> dict`
- Produces: `write_replay_artifact(document: dict, path: str | Path, *, expected_source_url: str, expected_completed_pages: int | None) -> ReplayValidationResult`
- Produces: `load_replay_artifact(path: str | Path, *, expected_source_url: str = "", expected_completed_pages: int | None = None) -> dict`
- Produces: `validate_replay_document(document: dict, *, expected_source_url: str = "", expected_completed_pages: int | None = None) -> ReplayValidationResult`

- [ ] **Step 1: Write failing safety and round-trip tests**

Add fixtures containing `Authorization: Bearer SECRET`, `Cookie`, `Set-Cookie`, and `X-API-Key`, plus `X-Robots-Tag`, `Cache-Control`, HSTS, and CSP. Assert forbidden names/`SECRET` are absent after decoding while allowed headers remain. Assert stable page/link ordering and the required schema/count fields.

- [ ] **Step 2: Run RED tests**

Run: `py -3.12 -m pytest tests/phase12/test_replay_roundtrip.py tests/phase12/test_replay_sensitive_fields.py -q`

Expected: collection/import failure because `audit_rules.replay` does not exist.

- [ ] **Step 3: Implement the minimal schema, allowlists, sanitizer, deterministic gzip writer, and loader**

Use explicit page/link/root fields derived from `server.EXPORT_FIELDS`, sitemap-fill output, `PageContext.from_export`, raw-adapter reads, and link-graph consumers. Serialize with `json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(",", ":"))`; write gzip without adding random data.

- [ ] **Step 4: Run GREEN safety and round-trip tests**

Run the Step 2 command and require all tests to pass.

- [ ] **Step 5: Write failing integrity tests**

Cover unsupported schema, wrong source URL, count mismatch, duplicate/empty page URLs, missing required collections, completed-page mismatch, and decoded credential-like keys/values.

- [ ] **Step 6: Run integrity RED tests**

Run: `py -3.12 -m pytest tests/phase12/test_replay_integrity.py -q`

Expected: failures showing the missing validation behavior.

- [ ] **Step 7: Implement minimal validation and typed result/error semantics**

Validation errors must identify the contract field without echoing sensitive values. The write path must unlink or leave unregistered an invalid artifact.

- [ ] **Step 8: Run Task 1 tests**

Run: `py -3.12 -m pytest tests/phase12/test_replay_roundtrip.py tests/phase12/test_replay_sensitive_fields.py tests/phase12/test_replay_integrity.py -q`

Expected: PASS.

### Task 2: Real normalized provider evidence and offline full-pipeline replay

**Files:**
- Modify: `audit_rules/replay.py`
- Create: `tests/phase12/test_replay_full_pipeline.py`
- Create: `tests/phase12/test_replay_provider_evidence.py`

**Interfaces:**
- Produces: `build_provider_evidence(audit_runner) -> dict`
- Produces: `replay_pipeline_inputs(document: dict) -> tuple[dict, dict]`

- [ ] **Step 1: Write failing provider and full-pipeline tests**

Use real `PerformanceSnapshot` dataclasses with no HTTP and explicit pending statuses for absent providers. Write a known crawl fixture, delete the original in-memory objects, load from disk, run the current RuleRunner pipeline, assert exactly 80 coverage rows, and compare representative robots/redirect/internal-link findings with the direct-input path.

- [ ] **Step 2: Run RED tests**

Run: `py -3.12 -m pytest tests/phase12/test_replay_provider_evidence.py tests/phase12/test_replay_full_pipeline.py -q`

Expected: failures for missing provider/pipeline replay interfaces.

- [ ] **Step 3: Implement normalized evidence conversion and pipeline input mapping**

PageSpeed snapshots are stable-sorted, dataclass-normalized evidence. Do not serialize provider objects, environment values, raw responses, request headers, or credentials. Preserve pending statuses for GSC, Semrush, GA4, server logs, and WordPress privileged sources.

- [ ] **Step 4: Run Task 2 tests**

Run the Step 2 command and require PASS with no network access.

### Task 3: V3-only runner registration and explicit failure semantics

**Files:**
- Modify: `runner.py`
- Create: `tests/phase12/test_replay_artifact_registration.py`
- Modify: `tests/phase12/test_artifact_pipeline_validation.py`
- Modify: `scripts/validate_v3_artifacts.py`

**Interfaces:**
- Consumes: Task 1 writer/validator and Task 2 provider evidence.
- Produces: registered artifact kind `audit_replay`, included by the existing ZIP registry.

- [ ] **Step 1: Write failing runner registration tests**

Assert a V3-enabled final input registers one validated replay artifact, V3-disabled execution registers none, ZIP validation includes it, page parity is enforced, and writer/validation failure records `v3_artifact_failed` plus `v3_artifacts_partial` without registering invalid output.

- [ ] **Step 2: Run RED tests**

Run: `py -3.12 -m pytest tests/phase12/test_replay_artifact_registration.py tests/phase12/test_artifact_pipeline_validation.py -q`

Expected: replay artifact assertions fail because runner wiring is absent.

- [ ] **Step 3: Implement minimal runner helper and V3 wiring**

Build the artifact from the already-final merged pages/links/site/reconciliation/completeness and current audit runner provider state. Write/reload/validate before `state.add_artifact`. On failure call the existing typed V3 artifact failure recorder with artifact `audit_replay` and a sanitized exception type.

- [ ] **Step 4: Run Task 3 tests**

Run the Step 2 command and require PASS.

### Task 4: Full local verification, feature commit, push, and CI gate

**Files:**
- Verify all files from Tasks 1-3.

- [ ] **Step 1: Run the complete fresh local suite**

Run: `py -3.12 -m pytest tests/ -q`

- [ ] **Step 2: Run formal offline checks**

Run Python compile over `audit_rules scripts server.py runner.py pdf_report.py state.py`; validate the 80-rule registry IDs/classifications, every tracked JSON file, `docker compose config -q`, the repository security checks, and the 5,000-page benchmark.

- [ ] **Step 3: Review diff and secret hygiene**

Run `git diff --check`, inspect the scoped diff, and scan tracked/staged files for credential/private-key patterns without printing secret values.

- [ ] **Step 4: Commit the feature**

Stage only the replay module, replay tests, runner integration, and validation script changes. Commit as `feat: add versioned audit replay artifact`.

- [ ] **Step 5: Push normally and wait for both Draft PR CI runs**

Run `git push origin feat/master-audit-completion`; do not force. Confirm PR #1 remains Draft and both push/pull-request Offline CI runs succeed before production access.

### Task 5: Single real crawl and final acceptance

**Files:**
- Generate ignored local artifacts under `reports/`.
- Modify: `docs/PRODUCTION_ACCEPTANCE_REPORT.md`

- [ ] **Step 1: Start exactly one chunked crawl after CI is green**

Use target `https://www.baolaipackaging.com/`, `total_max_pages=1000`, `chunk_target_pages=25`, `politeness="polite"`, `fill_sitemap_orphans=true`, and `sitemap_fill_cap=500`. Monitor for traps, query/facet/calendar/session explosion, 429s, abnormal 5xx, or abnormal growth; stop safely if observed.

- [ ] **Step 2: Require replay completeness before cleanup**

When done, verify audit completeness/truncation, load the registered replay artifact, require replay pages equal completed crawl pages, verify non-empty unique URLs/link graph/site data, and calculate SHA-256. If this fails, stop with `REPLAY_ARTIFACT_INCOMPLETE` and do not claim a final bundle.

- [ ] **Step 3: Download ZIP with auto-cleanup and save locally**

Call the audit ZIP operation with `auto_cleanup=True`, immediately decode its base64 to the exact returned filename under local `reports/`, verify returned SHA-256 and ZIP CRC, then inspect only the saved local copy.

- [ ] **Step 4: Perform final artifact and human acceptance validation**

Verify parseability/UTF-8, exactly 80 coverage rows/IDs, original 53 false-positive mappings, fresh P0/P1 groups, task usability, manual-review equivalent fields, deterministic score replay, PDF visual rendering, snapshot A/controlled synthetic B diff, provider truthfulness, no secrets, no mock evidence, and every expected legacy/V3/replay artifact.

- [ ] **Step 5: Run fresh final regression and update the report**

Repeat the full suite/formal checks/benchmark. Add `FINAL CURRENT-HEAD FULL RECRAWL` to `docs/PRODUCTION_ACCEPTANCE_REPORT.md` with every metric required by the approved acceptance specification and end with only `READY_TO_MERGE` or `NOT_READY_TO_MERGE`.

- [ ] **Step 6: Commit report, push, wait for CI, and stop**

Commit report-only changes as `docs: finalize post-fix production acceptance`, push normally, wait for Draft PR CI green, verify clean status, and report the 22 requested fields. Never merge PR #1.
