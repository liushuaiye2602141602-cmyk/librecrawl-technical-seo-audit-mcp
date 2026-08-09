# Final Production Acceptance Plan

## Purpose and decision boundary

This plan proves whether the current Master SEO Audit System can be used as a real website audit tool. It is an acceptance exercise, not a new development phase. Draft PR #1 remains Draft throughout this work and is never merged automatically.

The final acceptance report must return exactly one merge recommendation: `READY_TO_MERGE` or `NOT_READY_TO_MERGE`. Even `READY_TO_MERGE` is advisory only; merging remains a separate user decision.

## 1. Offline CI scope

Create one minimal workflow at `.github/workflows/ci.yml`, in its own commit. It will run for pull requests and pushes on Ubuntu using Python 3.12, matching the production Docker image and remaining within the project's documented Python support range.

The workflow must:

- install `requirements.txt` and pytest;
- run the complete suite with `python -m pytest tests/ -q`, with an expected baseline of 771 tests;
- compile the Python entry points and packages with `python -m compileall`;
- run the 80-rule registry integrity tests and explicitly verify exact IDs 1 through 80;
- parse every tracked JSON configuration/document file;
- run `docker compose config -q` without starting or contacting any service.

CI is fully offline and mock-safe. It receives no secrets and must not call PageSpeed Insights, GSC, Semrush, GA4, the production website, or any paid/external API. It must not start the Compose services.

## 2. Production acceptance crawl

Target: `https://www.baolaipackaging.com/`

Use exactly these request-level settings:

```text
total_max_pages=1000
chunk_target_pages=25
politeness="polite"
fill_sitemap_orphans=true
sitemap_fill_cap=500
```

These values apply only to this production-acceptance smoke crawl. They must not be written into project defaults, rule-engine limits, or permanent architecture. The Master Audit System must continue to support complete audits larger than 1,000 pages. `chunk_target_pages=25` is a processing window, not a total limit, and `sitemap_fill_cap=500` is a temporary request-protection parameter, not a permanent sitemap ceiling.

## 3. Crawl safety and completeness language

Use the existing polite controller without aggressive concurrency, rate-limit bypasses, aggressive retries, or deliberate duplicate requests.

Monitor progress for crawl traps, faceted explosions, infinite parameter spaces, calendar pagination, duplicate session/query URLs, and abnormal request growth. If one appears, stop safely before the page ceiling and record the exact reason.

If the site finishes naturally before 1,000 pages, record the observed completeness state. If the crawl reaches 1,000 pages while URLs remain, record `CRAWL_TRUNCATED_BY_ACCEPTANCE_SAFETY_LIMIT`. In that case, neither the artifacts nor the acceptance report may claim `FULL SITE CRAWL COMPLETE`.

The report must record pages discovered, pages fetched, sitemap URL count, sitemap-orphan fills, truncation status, request/error summary, and runtime.

## 4. PageSpeed Insights policy

When a process-only `PAGESPEED_API_KEY` is available, PSI may sample at most five representative URLs using the mobile strategy and the existing provider cache. It must never run across all crawled pages.

When no usable key is available, record `LIVE_PSI_VALIDATION_PENDING`. Never fabricate PSI evidence. The key must not be written to workflow files, repository files, logs, generated reports, or Git history.

## 5. Other provider policy

GSC, Semrush, GA4, WordPress privileged evidence, server logs, rendered-browser evidence, and availability evidence may be live-tested only when authoritative credentials or host-bound data already exist. Missing evidence remains `NOT_CHECKED` with `LIVE_VALIDATION_PENDING`. Provider failures must not become SEO failures or synthetic PASS results.

## 6. Artifact validation

Validate the real production chain:

```text
crawl
-> sitemap reconciliation
-> 80-rule evaluation
-> coverage
-> remediation tasks
-> manual review
-> audit score
-> available provider evidence
-> Markdown
-> PDF
-> ZIP
```

The saved local ZIP is the sole acceptance deliverable after the ephemeral server session is cleaned. Verify SHA-256, normal ZIP extraction, UTF-8 decoding, CSV parsing, expected filenames, absence of secrets, and continued legacy artifact availability.

The required V3 artifacts are:

- `coverage.csv`;
- `master-audit-tasks.csv`;
- the formal manual-review artifact (`manual-review.csv`, or the current host-bound `manual-review.md` equivalent, whose exact filename and fields must be recorded);
- `audit-score.json`;
- `performance.csv` when PSI data is genuinely available;
- portable audit snapshot;
- crawl diff from the real snapshot plus a controlled synthetic modification;
- enhanced Markdown report;
- enhanced PDF report;
- final ZIP;
- all compatible legacy artifacts.

The PDF must be opened structurally, rendered to images, and visually checked for clipped content, overlaps, missing glyphs, broken tables, and unreadable sections. The report must clearly expose Executive Summary, P0/P1/P2/P3, 80 Rule Coverage, Technical SEO, Performance, Search Data availability, International SEO, Schema, WordPress, Security, Manual Review, Missing External Data, Audit Score, and Remediation.

## 7. Coverage truth requirements

`coverage.csv` must contain exactly 80 rule rows, excluding its header. Verify these invariants:

- `NOT_CHECKED` is not PASS;
- `NOT_APPLICABLE` is not PASS or FAIL;
- a provider error is not an SEO FAIL;
- missing provider evidence never raises coverage or score;
- PASS, FAIL, WARNING, OPPORTUNITY, NOT_CHECKED, NOT_APPLICABLE, INTENTIONAL, and MANUAL semantics remain distinguishable where the current model uses them.

If the crawl is truncated, coverage and confidence must reflect the incomplete evidence rather than implying whole-site certainty.

## 8. Human acceptance review

Review every Critical/High and P0/P1 output row. For each, inspect the rule, URL or entity, evidence, detected value, expected value, confidence, remediation, owner, and acceptance criteria.

Specifically search for:

- obvious false positives;
- incorrect severity or priority;
- duplicate remediation tasks;
- incorrect or mismatched evidence;
- weak or non-actionable remediation;
- missing owner or acceptance criteria;
- inconsistent confidence;
- loss of affected URLs during task aggregation;
- manual-review instructions that do not tell a reviewer what evidence to collect and what decision to record;
- inconsistency between audit score, coverage, and confidence.

Real website defects remain in the report even when they prevent a clean-looking result.

## 9. Fix policy

Change implementation code only for a confirmed systemic false positive or implementation defect. Every such fix must follow:

```text
failing fixture
-> failing regression test for the observed behavior
-> minimal implementation fix
-> focused passing test
-> complete regression suite
```

Do not downgrade, delete, or hide a genuine website issue to make acceptance pass. Each acceptance fix is committed separately with its fixture and regression test. If no systemic defect is found, no implementation fix commit is created.

## 10. CI and Git policy

- Keep Draft PR #1 in Draft state.
- Do not merge the PR.
- Do not rebase, squash, force push, reset, or rewrite history.
- Put the CI workflow in an independent commit.
- Put each confirmed acceptance defect fix in an independent commit.
- Put the final acceptance report in a final documentation commit.
- Push only normal fast-forward updates to `origin/feat/master-audit-completion`.
- Do not change the approved crawl settings into system defaults.

## 11. Snapshot and diff smoke

Export and load the real acceptance snapshot and verify its schema version. Create a controlled synthetic copy without changing the production website. The synthetic comparison must exercise and correctly report at least:

- URL added;
- URL removed;
- HTTP status change;
- canonical change;
- indexability change.

No synthetic values may be mixed into the production findings or production score.

## 12. Secret scan

Freshly scan tracked files, Git diff/history for the acceptance commits, workflow files, extracted artifacts, reports, snapshots, logs, and ZIP contents for API keys, OAuth secrets, passwords, access tokens, private keys, and local credentials. Give specific attention to PageSpeed, Semrush, GSC, and GA4 variables. Redacted variable names and empty configuration placeholders are allowed; values are not.

## 13. Full regression gate

After CI and after any acceptance fix, freshly run the complete local verification set:

- `python -m pytest tests/ -q`;
- Python compile validation;
- all tracked JSON parsing;
- `docker compose config -q`;
- exact 80-rule registry and 72-adapter integrity;
- provider and MCP registration checks;
- security/direct-network and secret scans;
- the 100/1,000/5,000-page offline benchmark;
- production-image import and artifact validation where Docker is available.

Historical results are not sufficient evidence.

## 14. Final acceptance report

Create `docs/PRODUCTION_ACCEPTANCE_REPORT.md` containing:

1. Git HEAD and Draft PR number/status;
2. CI status;
3. production audit URL and exact request settings;
4. crawl result and completeness/truncation state;
5. pages discovered/fetched, sitemap counts, orphan fills, errors, and runtime;
6. exact 80-rule coverage verification;
7. P0/P1 findings review;
8. false positives discovered;
9. fixes made during acceptance;
10. manual-review validation;
11. score/coverage/confidence validation;
12. artifact, PDF, ZIP, CSV, UTF-8, and filename validation;
13. snapshot/diff validation;
14. provider live validations completed;
15. provider live validations pending;
16. secret-scan results;
17. final tests, compile, JSON, Compose, registry, security, and benchmark results;
18. known limitations and remaining blockers.

The report concludes with exactly one recommendation: `READY_TO_MERGE` or `NOT_READY_TO_MERGE`.

## 15. Acceptance gates

The system may be marked `READY_TO_MERGE` only when all of the following are evidenced:

- Draft PR CI is green and fully offline;
- the approved polite production crawl completes or its safety truncation is truthfully recorded;
- exactly 80 coverage rows are present with truthful missing-evidence semantics;
- P0/P1 human review finds no unresolved systemic false positive;
- manual review, scoring, tasks, artifacts, PDF, ZIP, snapshot, and diff contracts validate;
- generated and tracked materials contain no secrets;
- fresh full regression is green;
- every pending live provider is explicitly disclosed;
- no unresolved P0/P1 code or artifact defect remains.

Any failed gate yields `NOT_READY_TO_MERGE`. In either case, stop after pushing necessary CI, fixes, and the acceptance report. Never merge Draft PR #1 without explicit final user approval.
