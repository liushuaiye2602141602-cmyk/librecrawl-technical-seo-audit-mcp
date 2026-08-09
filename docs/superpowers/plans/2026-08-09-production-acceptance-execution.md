# Production Acceptance Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the current Master SEO Audit System is production-usable through offline CI, one bounded polite live crawl, human artifact review, snapshot/diff smoke testing, and a final evidence-backed merge recommendation.

**Architecture:** Add one secretless GitHub Actions workflow and a contract test for it, wait for Draft PR #1 CI, then drive the existing chunked MCP audit against the approved target. Keep generated evidence outside Git, inspect the real artifacts locally, apply only TDD-backed systemic fixes, and commit a final acceptance report.

**Tech Stack:** GitHub Actions, Ubuntu, Python 3.12, pytest, Docker Compose config validation, existing LibreCrawl MCP tools, CSV/JSON/ZIP standard-library validation, Poppler/pdfplumber PDF validation, existing snapshot/diff engine, GitHub CLI.

## Global Constraints

- Work only on `feat/master-audit-completion`; Draft PR #1 remains Draft and unmerged.
- No force push, rebase, reset, squash, history rewrite, branch deletion, or release tag.
- Production target is `https://www.baolaipackaging.com/`.
- Crawl request only: `total_max_pages=1000`, `chunk_target_pages=25`, `politeness="polite"`, `fill_sitemap_orphans=true`, `sitemap_fill_cap=500`.
- Approved crawl values must never become system defaults, hard limits, or rule-engine caps.
- CI is offline, secretless, and may not contact live providers or production sites.
- PSI is mobile-only, cached, and limited to five representative URLs when a real process-only key is available.
- Missing external provider evidence remains `NOT_CHECKED` / `LIVE_VALIDATION_PENDING`; never fabricate evidence.
- Generated crawl artifacts stay local and untracked except for a deliberately small regression fixture required by a confirmed code defect.
- Every implementation defect fix follows failing fixture -> failing regression -> minimal fix -> focused pass -> full regression.

---

### Task 1: Add minimal offline CI as an independent commit

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `tests/phase12/test_ci_workflow.py`

**Interfaces:**
- Consumes: `requirements.txt`, `tests/`, `audit_rules.registry.load_registry`, tracked project JSON, `docker-compose.yml`.
- Produces: one `offline-validation` GitHub Actions job and a contract test that prevents accidental live-network/secrets drift.

- [ ] **Step 1: Write the failing workflow contract test**

Create assertions that `.github/workflows/ci.yml` exists, uses `ubuntu-latest` and Python `3.12`, runs pytest/compile/registry/JSON/Compose config checks, defines no secret interpolation, and contains no live audit/provider command.

- [ ] **Step 2: Verify the contract test fails for the missing workflow**

Run: `python -m pytest tests/phase12/test_ci_workflow.py -q`

Expected: FAIL because `.github/workflows/ci.yml` does not exist.

- [ ] **Step 3: Create the minimal workflow**

Use checkout and setup-python actions, install `requirements.txt` plus pytest, and run these offline gates:

```bash
python -m pytest tests/ -q
python -m compileall -q audit_rules scripts server.py runner.py pdf_report.py state.py
python -m pytest tests/test_registry_integrity.py tests/test_master_id_adapter_binding.py -q
python -c "import json,pathlib; files=[p for p in pathlib.Path('.').rglob('*.json') if not any(x in p.parts for x in ('.git','.venv','venv','node_modules','.generated','reports','__pycache__'))]; [json.loads(p.read_text(encoding='utf-8')) for p in files]; print(f'validated_json={len(files)}')"
docker compose config -q
```

- [ ] **Step 4: Run the workflow contract and the local CI-equivalent gates**

Run the contract test, full suite, compile, registry, JSON, and Compose commands. All commands must exit 0.

- [ ] **Step 5: Commit and push CI**

```bash
git add .github/workflows/ci.yml tests/phase12/test_ci_workflow.py
git commit -m "ci: add offline production acceptance checks"
git push origin feat/master-audit-completion
```

### Task 2: Wait for Draft PR #1 CI

**Files:** None.

**Interfaces:**
- Consumes: GitHub check runs for Draft PR #1 at the CI commit SHA.
- Produces: recorded `CI_PASS` evidence or a concrete failure diagnosis.

- [ ] **Step 1: Confirm PR remains Draft and the expected workflow run starts**

Run: `gh pr view 1 --repo liushuaiye2602141602-cmyk/librecrawl-technical-seo-audit-mcp --json isDraft,headRefOid,statusCheckRollup,url`

- [ ] **Step 2: Wait for completion**

Run: `gh pr checks 1 --repo liushuaiye2602141602-cmyk/librecrawl-technical-seo-audit-mcp --watch --interval 10`

Expected: all checks complete successfully. Do not begin the production crawl while CI is pending or red.

- [ ] **Step 3: If CI fails, reproduce and fix minimally**

Read the failed job log. For a real cross-platform defect, add a failing regression before the minimal implementation fix. For workflow-only syntax/configuration, modify only the workflow contract and YAML. Re-run all local CI gates, commit, push, and wait again.

### Task 3: Run the bounded production acceptance crawl

**Files:** Local ignored reports/artifacts only.

**Interfaces:**
- Consumes: `librecrawl_start_chunked_audit`, `librecrawl_audit_status`, `librecrawl_audit_zip` with the approved settings.
- Produces: one SHA-256-verified local ZIP and an ephemeral server session that is deleted with `auto_cleanup=true`.

- [ ] **Step 1: Verify output hygiene and Git cleanliness**

Run `git status --short`, inspect ignore rules for reports/ZIP/PDF/CSV/snapshots/cache, and choose a local ignored acceptance-output directory.

- [ ] **Step 2: Configure only process-level acceptance flags**

Enable V3 for the running audit process, limit PSI to five mobile URLs if the supplied key can be used process-only, and leave unavailable providers without fabricated credentials.

- [ ] **Step 3: Start exactly one chunked crawl**

Call `librecrawl_start_chunked_audit` with the target and approved five request parameters.

- [ ] **Step 4: Poll safely every 20-30 seconds**

Record pages discovered/fetched, response classes, sitemap counts/fills, delay, errors, runtime, and trap indicators. Stop early on URL explosion or substantial 429/5xx behavior. Record `CRAWL_TRUNCATED_BY_ACCEPTANCE_SAFETY_LIMIT` at an incomplete 1,000-page ceiling.

- [ ] **Step 5: Download with cleanup and verify the local copy**

Call `librecrawl_audit_zip(auto_cleanup=true)`, decode `content_base64` immediately, save the exact response filename locally, verify SHA-256, and confirm the server session was cleaned.

- [ ] **Step 6: Recheck Git status**

Run `git status --short`; no generated production artifact may appear as a repository change.

### Task 4: Validate real artifacts and findings

**Files:** Extracted local ignored artifacts.

**Interfaces:**
- Consumes: downloaded production ZIP and contained V3/legacy artifacts.
- Produces: structured acceptance evidence for coverage, findings, manual workflow, score, tasks, reports, and provider states.

- [ ] **Step 1: Validate ZIP, filenames, encoding, CSV, and JSON**

Use `ZipFile.testzip()`, parse every CSV, decode text as UTF-8/UTF-8-SIG, parse JSON, require non-empty applicable files, and scan every member for real credentials.

- [ ] **Step 2: Validate coverage truth**

Require 80 unique data rows with IDs exactly 1..80. Programmatically verify status/result invariants, evaluated/eligible counts, sampling semantics, and provider-error handling.

- [ ] **Step 3: Review every P0/P1/Critical/High finding**

Extract rule, URL, evidence, detected/expected values, severity/priority, confidence, remediation, owner, and acceptance criteria. Classify each as `TRUE_SITE_ISSUE`, `SYSTEM_FALSE_POSITIVE`, `DUPLICATE_FINDING`, `WRONG_SEVERITY`, `INSUFFICIENT_EVIDENCE`, or `EXPECTED_INTENTIONAL_BEHAVIOR`.

- [ ] **Step 4: Validate manual-review usability**

Require all eight manual rules and verify why-manual context, required evidence, review instructions, acceptance criteria, and a writable review status/decision path.

- [ ] **Step 5: Validate score determinism and truth semantics**

Require distinct Score/Coverage/Confidence outputs, ensure missing providers are excluded rather than passed, and recompute from identical inputs to require identical output.

- [ ] **Step 6: Validate task usability**

Check aggregation, duplicate suppression, affected URL preservation, priority, evidence, owner, remediation, acceptance criteria, and confidence.

- [ ] **Step 7: Validate Markdown and PDF human usability**

Parse Markdown headings. Use PDF metadata/text extraction plus Poppler page rendering and visual inspection to verify legibility, section hierarchy, missing-data prominence, actionable findings, and absence of clipping/overlap/broken glyphs.

### Task 5: Validate snapshot and diff behavior

**Files:** Local ignored real Snapshot A, synthetic Snapshot B, and diff output.

**Interfaces:**
- Consumes: the production portable snapshot and existing snapshot load/diff implementation.
- Produces: validated schema/load result and a deterministic diff covering all required mutation classes.

- [ ] **Step 1: Load and validate Snapshot A**

Require the formal schema version, audited host binding, and valid page index.

- [ ] **Step 2: Build controlled synthetic Snapshot B locally**

Copy Snapshot A and change data only: add one URL, remove one URL, change one status 200->404, indexable->noindex, canonical, and title.

- [ ] **Step 3: Run the real diff engine**

Require the current formal classifications (`FIXED`, `REGRESSED`, `NEW_ISSUE`, `INFORMATIONAL_CHANGE` as applicable) and a valid crawl-diff artifact. Do not mix synthetic findings into the production score/report.

### Task 6: Apply only confirmed systemic fixes

**Files:** Conditional fixture, regression test, and minimal affected implementation file.

**Interfaces:**
- Consumes: a Task 4 classification of `SYSTEM_FALSE_POSITIVE`, implementation-caused `WRONG_SEVERITY`/`INSUFFICIENT_EVIDENCE`, or `SYSTEMIC_DUPLICATION`.
- Produces: one independently committed TDD fix per systemic defect, or no code change when findings are genuine.

- [ ] **Step 1: Capture the smallest privacy-safe fixture**

Remove site identities and credentials while preserving the exact behavior.

- [ ] **Step 2: Write and run the failing regression**

The test must fail for the observed reason before implementation changes.

- [ ] **Step 3: Implement the minimal fix and verify focused tests**

Change only the responsible logic; do not weaken rules or hide a true site issue.

- [ ] **Step 4: Run the full regression, commit, push, and wait for CI**

Use a separate fix commit, normal push, and require Draft PR CI to return green again.

### Task 7: Write and publish the final acceptance report

**Files:**
- Create: `docs/PRODUCTION_ACCEPTANCE_REPORT.md`

**Interfaces:**
- Consumes: fresh CI, crawl, artifact, review, snapshot/diff, provider, secret-scan, and regression evidence.
- Produces: the complete production acceptance record ending in one merge recommendation.

- [ ] **Step 1: Run fresh full regression and benchmark**

Run full pytest, compile, registry/adapters/providers/tools integrity, tracked JSON validation, Compose config, security/direct-network scan, secret scan, 100/1,000/5,000-page benchmark, and production-image artifact validation.

- [ ] **Step 2: Write all required report sections**

Record date, branch, HEAD, PR/CI, target/settings, crawl metrics/completeness, coverage, P0/P1 review, false positives/fixes, manual/score/task usability, artifacts/PDF/ZIP, snapshot/diff, provider RUN/PENDING states, secret scan, regression, limitations, and remaining external requirements.

- [ ] **Step 3: Select the evidence-backed result**

Use `READY_TO_MERGE` only if every gate in `docs/PRODUCTION_ACCEPTANCE_PLAN.md` passes; otherwise use `NOT_READY_TO_MERGE` and list blockers.

- [ ] **Step 4: Commit and push the report**

```bash
git add docs/PRODUCTION_ACCEPTANCE_REPORT.md
git commit -m "docs: record production acceptance result"
git push origin feat/master-audit-completion
```

- [ ] **Step 5: Wait for final CI and stop**

Require local validation and Draft PR CI to be green, verify a clean working tree, leave PR #1 Draft, and do not merge or delete any branch.
