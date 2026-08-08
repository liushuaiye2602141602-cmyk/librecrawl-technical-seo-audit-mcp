# Rule 74 Snapshot/Diff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement portable versioned crawl snapshots, deterministic before/after diffing, Rule 74 findings, honest no-baseline coverage, and snapshot/diff artifacts without relying on persistent audit session IDs.

**Architecture:** Snapshot construction and gzip I/O live in `audit_rules/snapshot.py`; comparison and CSV serialization live in `audit_rules/snapshot_diff.py`; the pure Rule 74 adapter consumes already-computed diff records from the runner data dictionary. The integration layer accepts an optional baseline snapshot and returns additive snapshot/diff artifacts, while missing baseline data leaves Rule 74 `NOT_CHECKED + UNKNOWN`.

**Tech Stack:** Python 3.14, standard-library `dataclasses`, `hashlib`, `json`, `gzip`, `csv`, `pathlib`, existing `RuleDefinition`/`Finding`/`PageContext`/`SiteContext`, pytest 9.

## Global Constraints

- Snapshot filename is `audit-snapshot-v1.json.gz`; schema version is integer `1`.
- Snapshot comparison never depends on `session_id` persistence.
- Rule functions perform no file or network I/O.
- Missing baseline is `NOT_CHECKED + UNKNOWN`, never `PASS`.
- Snapshot and diff ordering is deterministic.
- Readers ignore unknown additive fields in schema version 1 and reject unsupported major versions.
- Existing MCP signatures and legacy artifacts remain unchanged.
- The untracked `.agents/` directory is user-owned and must not be staged.

---

### Task 1: Versioned Snapshot Schema and Gzip I/O

**Files:**

- Create: `audit_rules/snapshot.py`
- Create: `tests/phase4b/test_snapshot.py`

**Interfaces:**

- Produces: `SnapshotValidationError(ValueError)`
- Produces: `build_snapshot(site_ctx: SiteContext, page_contexts: list[PageContext], *, created_at: str | None = None) -> dict`
- Produces: `build_snapshot_from_export(export_data: dict, base_url: str = "", *, created_at: str | None = None) -> dict`
- Produces: `validate_snapshot(snapshot: dict) -> None`
- Produces: `write_snapshot(snapshot: dict, path: str | Path) -> Path`
- Produces: `load_snapshot(path: str | Path) -> dict`
- Consumes: existing `LibreCrawlDataProvider.create_contexts()` and context models.

- [ ] **Step 1: Write failing schema and determinism tests**

```python
def test_build_snapshot_has_v1_contract(site_ctx, pages):
    from audit_rules.snapshot import build_snapshot
    snapshot = build_snapshot(site_ctx, pages, created_at="2026-08-09T00:00:00Z")
    assert snapshot["schema_version"] == 1
    assert snapshot["base_url"] == "https://example.com"
    assert [p["url"] for p in snapshot["pages"]] == sorted(p.url for p in pages)
    assert set(snapshot["pages"][0]) >= {
        "url", "status", "indexable", "robots", "title",
        "meta_description", "h1", "canonical", "hreflang",
        "schema_fingerprint", "content_fingerprint",
        "internal_links", "technical_signals",
    }

def test_snapshot_is_deterministic(site_ctx, pages):
    from audit_rules.snapshot import build_snapshot
    first = build_snapshot(site_ctx, list(reversed(pages)), created_at="2026-08-09T00:00:00Z")
    second = build_snapshot(site_ctx, pages, created_at="2026-08-09T00:00:00Z")
    assert first == second
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `C:\Users\liush\AppData\Local\Python\bin\python.exe -m pytest tests/phase4b/test_snapshot.py -q`

Expected: collection fails because `audit_rules.snapshot` does not exist.

- [ ] **Step 3: Implement normalized snapshot construction**

```python
SCHEMA_VERSION = 1
SNAPSHOT_FILENAME = "audit-snapshot-v1.json.gz"

class SnapshotValidationError(ValueError):
    pass

def build_snapshot(
    site_ctx: SiteContext,
    page_contexts: list[PageContext],
    *,
    created_at: str | None = None,
) -> dict:
    created = created_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    pages = [_normalize_page(ctx) for ctx in sorted(page_contexts, key=lambda p: p.url)]
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": created,
        "base_url": site_ctx.base_url,
        "site_profile": site_ctx.site_profile,
        "pages": pages,
        "summary": {
            "page_count": len(pages),
            "indexable_count": sum(1 for page in pages if page["indexable"]),
        },
    }
```

Normalize strings with whitespace collapsing; sort hreflang records; compute SHA-256 fingerprints from canonical JSON for schema and from `content_hash`, normalized body text, or title/H1/description fallback for content. Record internal-link counts plus a stable target fingerprint. Indexability is true only for 2xx pages without `noindex`.

- [ ] **Step 4: Write failing validation and gzip round-trip tests**

```python
def test_gzip_round_trip_ignores_additive_v1_fields(tmp_path, snapshot):
    from audit_rules.snapshot import load_snapshot, write_snapshot
    snapshot["future_optional_field"] = {"ok": True}
    path = write_snapshot(snapshot, tmp_path / "audit-snapshot-v1.json.gz")
    assert path.read_bytes()[:2] == b"\x1f\x8b"
    assert load_snapshot(path) == snapshot

def test_rejects_unsupported_schema_version(tmp_path, snapshot):
    from audit_rules.snapshot import SnapshotValidationError, write_snapshot
    snapshot["schema_version"] = 2
    with pytest.raises(SnapshotValidationError, match="Unsupported snapshot schema version"):
        write_snapshot(snapshot, tmp_path / "bad.json.gz")

def test_rejects_duplicate_urls(snapshot):
    from audit_rules.snapshot import SnapshotValidationError, validate_snapshot
    snapshot["pages"].append(dict(snapshot["pages"][0]))
    with pytest.raises(SnapshotValidationError, match="duplicate URL"):
        validate_snapshot(snapshot)
```

- [ ] **Step 5: Implement validation and deterministic gzip I/O**

Use `gzip.GzipFile(filename="", mode="wb", mtime=0)` so identical snapshots serialize identically. Validate root type, schema version, required root fields, page list type, required page fields, non-empty unique URLs, boolean `indexable`, and integer HTTP status. Load UTF-8 JSON, preserve unknown version-1 fields, and wrap JSON/gzip/type failures in `SnapshotValidationError` with the path.

- [ ] **Step 6: Run focused tests**

Run: `C:\Users\liush\AppData\Local\Python\bin\python.exe -m pytest tests/phase4b/test_snapshot.py -q`

Expected: all snapshot tests pass.

- [ ] **Step 7: Commit the schema unit**

```powershell
git add -- audit_rules/snapshot.py tests/phase4b/test_snapshot.py
git commit -m "feat: add versioned audit snapshots"
```

### Task 2: Deterministic Diff Engine and CSV Artifact

**Files:**

- Create: `audit_rules/snapshot_diff.py`
- Create: `tests/phase4b/test_snapshot_diff.py`

**Interfaces:**

- Consumes: validated dictionaries returned by `load_snapshot()`.
- Produces: `SnapshotChange` dataclass with `url`, `change_type`, `classification`, `field`, `before`, `after`, `evidence`.
- Produces: `diff_snapshots(before: dict, after: dict, *, include_unchanged: bool = False) -> list[SnapshotChange]`
- Produces: `write_crawl_diff_csv(changes: list[SnapshotChange], path: str | Path) -> Path`
- Produces: `crawl_diff_csv_to_string(changes: list[SnapshotChange]) -> str`

- [ ] **Step 1: Write failing minimum change-type tests**

```python
@pytest.mark.parametrize(
    ("mutation", "expected_type"),
    [
        (lambda pages: pages.append(make_page("https://e.test/new")), "URL_ADDED"),
        (lambda pages: pages.pop(0), "URL_REMOVED"),
        (lambda pages: pages[0].update(status=404), "STATUS_CHANGED"),
        (lambda pages: pages[0].update(indexable=False), "INDEXABILITY_CHANGED"),
        (lambda pages: pages[0].update(robots="noindex"), "ROBOTS_CHANGED"),
        (lambda pages: pages[0].update(canonical="https://e.test/other"), "CANONICAL_CHANGED"),
        (lambda pages: pages[0].update(title="Changed"), "TITLE_CHANGED"),
        (lambda pages: pages[0].update(meta_description="Changed"), "DESCRIPTION_CHANGED"),
        (lambda pages: pages[0].update(h1="Changed"), "H1_CHANGED"),
        (lambda pages: pages[0].update(hreflang=[{"lang": "de", "url": "https://e.test/de"}]), "HREFLANG_CHANGED"),
        (lambda pages: pages[0].update(schema_fingerprint="new"), "SCHEMA_CHANGED"),
        (lambda pages: pages[0].update(content_fingerprint="new"), "CONTENT_CHANGED"),
        (lambda pages: pages[0]["internal_links"].update(inbound_count=0), "INTERNAL_LINK_REGRESSION"),
    ],
)
def test_detects_required_change_types(before_snapshot, mutation, expected_type):
    from audit_rules.snapshot_diff import diff_snapshots
    after = copy.deepcopy(before_snapshot)
    mutation(after["pages"])
    assert expected_type in {change.change_type for change in diff_snapshots(before_snapshot, after)}
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `C:\Users\liush\AppData\Local\Python\bin\python.exe -m pytest tests/phase4b/test_snapshot_diff.py -q`

Expected: collection fails because `audit_rules.snapshot_diff` does not exist.

- [ ] **Step 3: Implement URL-indexed O(n) comparison**

```python
@dataclass(frozen=True)
class SnapshotChange:
    url: str
    change_type: str
    classification: str
    field: str
    before: object
    after: object
    evidence: str

def diff_snapshots(before: dict, after: dict, *, include_unchanged: bool = False) -> list[SnapshotChange]:
    validate_snapshot(before)
    validate_snapshot(after)
    before_by_url = {page["url"]: page for page in before["pages"]}
    after_by_url = {page["url"]: page for page in after["pages"]}
    changes: list[SnapshotChange] = []
    for url in sorted(before_by_url.keys() | after_by_url.keys()):
        before_page = before_by_url.get(url)
        after_page = after_by_url.get(url)
        if before_page is None:
            changes.append(_make_change(url, "URL_ADDED", "INFORMATIONAL_CHANGE", "url", None, url))
            continue
        if after_page is None:
            classification = "REGRESSED" if before_page["indexable"] else "INFORMATIONAL_CHANGE"
            changes.append(_make_change(url, "URL_REMOVED", classification, "url", url, None))
            continue

        page_changes = _diff_page(url, before_page, after_page)
        if page_changes:
            changes.extend(page_changes)
        elif include_unchanged:
            changes.append(_make_change(url, "PAGE_UNCHANGED", "UNCHANGED", "page", before_page, after_page))
    return sorted(changes, key=lambda c: (c.url, c.change_type, c.field))
```

Implement `_make_change()` as the only `SnapshotChange` factory and `_diff_page()` as a fixed-field comparison over status, indexability, robots, canonical, title, meta description, H1, hreflang, schema fingerprint, and content fingerprint, followed by the internal-link regression gate. Classification rules are explicit: indexable URL removal and good-to-bad status/indexability transitions are `REGRESSED`; bad-to-good transitions and missing-to-present critical metadata are `FIXED`; newly missing metadata is `NEW_ISSUE`; value-to-value metadata/content changes are `INFORMATIONAL_CHANGE`; identical pages produce `PAGE_UNCHANGED` with `UNCHANGED` only when requested.

- [ ] **Step 4: Add classification, unchanged, determinism, and scale tests**

```python
def test_status_recovery_is_fixed(before_snapshot):
    before_snapshot["pages"][0].update(status=404, indexable=False)
    after = copy.deepcopy(before_snapshot)
    after["pages"][0].update(status=200, indexable=True)
    classes = {(c.change_type, c.classification) for c in diff_snapshots(before_snapshot, after)}
    assert ("STATUS_CHANGED", "FIXED") in classes
    assert ("INDEXABILITY_CHANGED", "FIXED") in classes

def test_identical_snapshots_optionally_emit_unchanged(before_snapshot):
    assert diff_snapshots(before_snapshot, copy.deepcopy(before_snapshot)) == []
    changes = diff_snapshots(before_snapshot, copy.deepcopy(before_snapshot), include_unchanged=True)
    assert {(c.change_type, c.classification) for c in changes} == {("PAGE_UNCHANGED", "UNCHANGED")}

def test_diff_5000_pages_is_linear_shape(make_snapshot):
    before = make_snapshot(5000)
    after = copy.deepcopy(before)
    after["pages"][-1]["title"] = "Changed"
    assert [c.change_type for c in diff_snapshots(before, after)] == ["TITLE_CHANGED"]
```

- [ ] **Step 5: Add and implement CSV writer tests**

CSV columns are exactly `url,change_type,classification,field,before,after,evidence`. Complex values use deterministic compact JSON. Tests parse the CSV with `csv.DictReader`, assert row order, UTF-8 content, header order, and preservation of before/after evidence.

- [ ] **Step 6: Run focused tests**

Run: `C:\Users\liush\AppData\Local\Python\bin\python.exe -m pytest tests/phase4b/test_snapshot_diff.py -q`

Expected: all diff and CSV tests pass.

- [ ] **Step 7: Commit the diff unit**

```powershell
git add -- audit_rules/snapshot_diff.py tests/phase4b/test_snapshot_diff.py
git commit -m "feat: add crawl snapshot diff engine"
```

### Task 3: Rule 74 Adapter and Honest Coverage

**Files:**

- Create: `audit_rules/checks/snapshot_diff.py`
- Modify: `audit_rules/checks/__init__.py`
- Modify: `audit_rules/adapters.py`
- Modify: `audit_rules/runner.py`
- Modify: `audit_rules/coverage.py`
- Modify: `audit_specs/master_audit_mapping.csv`
- Modify: `tests/phase4a/test_new_auto_rule_set.py`
- Modify: `tests/test_existing_full_compatibility.py`
- Modify: `tests/test_master_id_adapter_binding.py`
- Modify: `tests/test_phase2_partial_rule_set.py`
- Modify: `tests/test_phase3_checks.py`
- Modify: `tests/test_registry_integrity.py`
- Create: `tests/phase4b/test_rule74_integration.py`

**Interfaces:**

- Consumes: `data["snapshot_changes"]: list[SnapshotChange]`.
- Produces: `check_regression_test(rule, site_ctx, page_contexts, data) -> list[Finding]`.
- Runner adds provider marker `SnapshotBaseline` only when validated snapshot changes were supplied.
- `RuleRunner.run_from_export()` accepts optional `existing_data` and merges it with crawl/extended data before dispatch.
- Coverage treats required source `SnapshotBaseline` like any unavailable source.

- [ ] **Step 1: Write failing adapter and no-baseline coverage tests**

```python
def test_rule74_without_baseline_is_not_checked(runner, export_data):
    _, coverage = runner.run_from_export(export_data, base_url="https://example.com")
    row = next(row for row in coverage if row.audit_id == 74)
    assert row.execution_status.value == "NOT_CHECKED"
    assert row.result_status.value == "UNKNOWN"
    assert "SnapshotBaseline" in row.not_checked_reason

def test_rule74_regression_becomes_warning(rule74, site_ctx, pages, regression_change):
    from audit_rules.checks.snapshot_diff import check_regression_test
    findings = check_regression_test(
        rule74, site_ctx, pages, {"snapshot_changes": [regression_change]},
    )
    assert len(findings) == 1
    assert findings[0].severity in {"Error", "Warning"}
    assert "before=" in findings[0].evidence
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `C:\Users\liush\AppData\Local\Python\bin\python.exe -m pytest tests/phase4b/test_rule74_integration.py -q`

Expected: Rule 74 has no adapter and the current coverage manager would incorrectly treat a registered empty automated check as pass.

- [ ] **Step 3: Implement the pure adapter and lazy registration**

Map `REGRESSED` to `Severity.ERROR` for URL removal, 4xx/5xx status, or loss of indexability; map other regressions/new issues to `Severity.WARNING`; map `FIXED` and `INFORMATIONAL_CHANGE` to `Severity.INFO`. Preserve change type, before/after values, classification, and evidence. Return an empty list when no `snapshot_changes` key exists; coverage semantics handle the missing source.

Add a `snapshot_diff` entry to `_import_all()`, add `_load_phase4b_checks()` in `adapters.py`, and bind `regression_test -> check_regression_test`.

- [ ] **Step 4: Update runner availability and CSV classification**

Extend `run_from_export(export_data, base_url="", existing_data=None)` to merge caller-supplied shared data with `extended_checks` and `crawl`. Add `SnapshotBaseline` to `available_providers` only when `existing_data["snapshot_baseline_available"] is True`; this distinguishes an identical before/after comparison (valid PASS with zero changes) from no baseline (NOT_CHECKED). Update exactly these Rule 74 columns in `master_audit_mapping.csv` while preserving every other field: `impl_status=EXISTING_PARTIAL`, `current_check_name=check_regression_test`, `current_module=audit_rules/checks/snapshot_diff.py`, `data_source=LibreCrawl + SnapshotBaseline`, `external_dependency=None`, and `detection_method=STATIC_ANALYSIS + CRAWL_COMPARISON`.

Keep `EXISTING_PARTIAL` because the first audit has no baseline and comparison coverage depends on an explicitly supplied snapshot.

- [ ] **Step 5: Update count/set integrity tests**

Expected post-migration facts:

```python
assert adapter_count == 48
assert classification_counts == {
    "EXISTING_FULL": 18,
    "EXISTING_PARTIAL": 33,
    "NEW_AUTO": 0,
    "NEW_EXTERNAL_DATA": 16,
    "NEW_MANUAL": 13,
}
```

Update all hardcoded adapter and classification assertions discovered by `rg "47|NEW_AUTO|EXISTING_PARTIAL" tests` only where they describe this source of truth.

- [ ] **Step 6: Run Rule 74 and integrity tests**

Run: `C:\Users\liush\AppData\Local\Python\bin\python.exe -m pytest tests/phase4b tests/phase4a/test_new_auto_rule_set.py tests/test_registry_integrity.py tests/test_master_id_adapter_binding.py tests/test_existing_full_compatibility.py tests/test_phase2_partial_rule_set.py tests/test_phase3_checks.py -q`

Expected: all focused and integrity tests pass.

- [ ] **Step 7: Commit Rule 74 integration**

```powershell
git add -- audit_rules/checks/snapshot_diff.py audit_rules/checks/__init__.py audit_rules/adapters.py audit_rules/runner.py audit_rules/coverage.py audit_specs/master_audit_mapping.csv tests/phase4b/test_rule74_integration.py tests/phase4a/test_new_auto_rule_set.py tests/test_existing_full_compatibility.py tests/test_master_id_adapter_binding.py tests/test_phase2_partial_rule_set.py tests/test_phase3_checks.py tests/test_registry_integrity.py
git commit -m "feat: integrate rule 74 snapshot regressions"
```

### Task 4: Snapshot/Diff Artifact Pipeline

**Files:**

- Modify: `audit_rules/integration.py`
- Modify: `runner.py`
- Modify: `.env.example`
- Modify: `tests/test_integration.py`
- Create: `tests/phase4b/test_snapshot_artifacts.py`

**Interfaces:**

- Produces: `build_snapshot_artifacts(export_data: dict, base_url: str, baseline_path: str | Path | None = None) -> tuple[bytes, list[SnapshotChange], str]` in `audit_rules.integration`.
- The function returns gzip bytes for the current snapshot, diff records, and CSV content; it performs no persistent writes.
- `runner.py` owns report-directory writes and state artifact registration.

- [ ] **Step 1: Write failing in-memory artifact tests**

```python
def test_build_snapshot_artifacts_without_baseline(export_data):
    from audit_rules.integration import build_snapshot_artifacts
    snapshot_gz, changes, diff_csv = build_snapshot_artifacts(
        export_data, "https://example.com", baseline_path=None,
    )
    assert snapshot_gz[:2] == b"\x1f\x8b"
    assert changes == []
    assert diff_csv == ""

def test_build_snapshot_artifacts_with_baseline(tmp_path, export_data, baseline):
    from audit_rules.integration import build_snapshot_artifacts
    snapshot_gz, changes, diff_csv = build_snapshot_artifacts(
        export_data, "https://example.com", baseline_path=baseline,
    )
    assert changes
    assert "change_type" in diff_csv
```

- [ ] **Step 2: Implement byte serialization and artifact builder**

Add `snapshot_to_gzip_bytes(snapshot: dict) -> bytes` and `snapshot_from_gzip_bytes(payload: bytes) -> dict` beside file I/O so integration tests do not create files. `build_snapshot_artifacts()` builds the current snapshot, optionally loads the baseline, diffs it, and serializes the CSV.

- [ ] **Step 3: Write failing finalize wiring test**

Patch `state.add_artifact` and a temporary `REPORTS_DIR`, run the finalize path with V3 enabled, and assert registration of `audit_snapshot` always and `crawl_diff_csv` only when `AUDIT_SNAPSHOT_BASELINE_PATH` points to a valid baseline. Assert corrupt baseline logs `snapshot_diff_failed` without breaking legacy artifacts.

- [ ] **Step 4: Wire additive artifacts in `runner.py`**

Before invoking the V3 pipeline, build the current snapshot and optional diff. Call `run_v3_pipeline()` with `existing_data={"snapshot_changes": changes, "snapshot_baseline_available": baseline_path is not None}`; the integration path forwards this data through `RuleRunner.run_from_export()`. After the V3 pipeline succeeds:

- create `<domain>-<timestamp>.audit-snapshot-v1.json.gz` and register `audit_snapshot`;
- if `AUDIT_SNAPSHOT_BASELINE_PATH` is configured, create `<domain>-<timestamp>.crawl-diff.csv` and register `crawl_diff_csv`;
- isolate snapshot/diff failures with a specific event while preserving the legacy audit.

Document `AUDIT_SNAPSHOT_BASELINE_PATH` and `AUDIT_SNAPSHOT_OUTPUT_DIR` in `.env.example`; neither contains a secret.

- [ ] **Step 5: Run focused integration tests**

Run: `C:\Users\liush\AppData\Local\Python\bin\python.exe -m pytest tests/phase4b/test_snapshot_artifacts.py tests/test_integration.py -q`

Expected: all artifact tests and existing feature-flag tests pass.

- [ ] **Step 6: Commit artifact wiring**

```powershell
git add -- audit_rules/snapshot.py audit_rules/integration.py runner.py .env.example tests/test_integration.py tests/phase4b/test_snapshot_artifacts.py
git commit -m "feat: wire snapshot and crawl diff artifacts"
```

### Task 5: Documentation, Full Regression, and Checkpoint

**Files:**

- Create: `docs/audit/SNAPSHOT_DIFF.md`
- Create: `docs/audit/PHASE4B_COMPLETION_REPORT.md`
- Modify: `README.md`
- Modify: `docs/handoff/CURRENT_RULE_MATRIX.csv`
- Modify: `docs/handoff/CURRENT_SYSTEM_STATE.json`
- Modify: `docs/handoff/REMAINING_IMPLEMENTATION_ROADMAP.md`

**Interfaces:** Documentation records the exact schema, CLI/API helpers, first-audit semantics, artifact names, classification counts, tests, and compatibility results.

- [ ] **Step 1: Document schema and operational workflow**

Include:

```text
Audit A -> export audit-snapshot-v1.json.gz
deploy/change site
Audit B -> export audit-snapshot-v1.json.gz
baseline snapshot + current snapshot -> crawl-diff.csv + Rule 74 findings
```

State that snapshots must be downloaded or stored on a mounted persistent path in containers, that unknown additive v1 fields are accepted, and that unsupported major versions are rejected.

- [ ] **Step 2: Regenerate handoff state from current sources**

Update the 80-row handoff matrix and machine-readable counts from the Registry, not by editing counters from memory. Mark Rule 74 `EXISTING_PARTIAL`, adapter count 48, `NEW_AUTO` 0, and snapshot/diff artifacts implemented.

- [ ] **Step 3: Run source and whitespace checks**

Run:

```powershell
git diff --check
rg -n "TODO|FIXME|NotImplemented|placeholder" audit_rules/snapshot.py audit_rules/snapshot_diff.py audit_rules/checks/snapshot_diff.py
```

Expected: no whitespace errors and no implementation placeholders.

- [ ] **Step 4: Run the full regression suite**

Run: `C:\Users\liush\AppData\Local\Python\bin\python.exe -m pytest tests/ -q`

Expected: all baseline and newly added tests pass, with 0 failures and any skips explicitly justified.

- [ ] **Step 5: Verify repository facts**

Run:

```powershell
git status --short
git diff --stat HEAD~1
C:\Users\liush\AppData\Local\Python\bin\python.exe -c "from collections import Counter; from audit_rules.registry import load_registry; from audit_rules.adapters import CompatibilityHarness; r=load_registry(); print(len(r), Counter(x.impl_status.value for x in r), len(CompatibilityHarness(r)._adapters))"
```

Expected: 80 registry rows, classifications `18/33/0/16/13`, 48 adapters, with only intentional workstream files plus user-owned `.agents/` visible.

- [ ] **Step 6: Commit documentation and completion report**

```powershell
git add -- README.md docs/audit/SNAPSHOT_DIFF.md docs/audit/PHASE4B_COMPLETION_REPORT.md docs/handoff/CURRENT_RULE_MATRIX.csv docs/handoff/CURRENT_SYSTEM_STATE.json docs/handoff/REMAINING_IMPLEMENTATION_ROADMAP.md
git commit -m "docs: complete rule 74 snapshot handoff"
```

- [ ] **Step 7: Continue to the next independent subsystem**

Create and execute the next plan for PageSpeed live validation, using the supplied API key only through a process-scoped environment variable. Never write or echo the secret into repository files, logs, reports, or commit history.
