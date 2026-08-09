# Production Acceptance Report

## 1. Final decision

`NOT_READY_TO_MERGE`.

The single authorized post-fix production crawl completed naturally and produced the current audit outputs, but the required `audit-replay-v1.json.gz` failed validation and was correctly deleted rather than registered. Consequently, crawl-page/replay-page parity cannot be proven and no final cleanup ZIP was requested. Two systemic issues were also confirmed after the crawl: the Rule 6 defect is fixed and green locally and in CI, while the Rule 1 evidence-contract issue remains unresolved. The production artifacts predate the Rule 6 fix.

Draft PR #1 remains OPEN and Draft. It was not merged, rebased, squashed, force-pushed, or marked ready.

## 2. Branch and Git revisions

- Branch: `feat/master-audit-completion`
- Crawl execution HEAD: `beb8e317ccfce78e0b6d84d3b418e085db9491a7`
- Replay false-positive fix: `a021cfb8e460c5cc11d7f7d42b2bff7c81bce915`
- Redirect-evidence normalization fix: `f4fb12c942a8045904cddaf4662eefabb614c639`
- Replay authorization-value validation fix: `acac52aa3a74fb61a7ae7eb4561773c1186a619e`
- PR: <https://github.com/liushuaiye2602141602-cmyk/librecrawl-technical-seo-audit-mcp/pull/1>

The crawl was deliberately not repeated after the post-crawl fixes because exactly one new real crawl was authorized. The missing replay artifact prevents an exact offline regeneration from all 315 normalized page inputs.

## 3. Why the recrawl was required

The earlier full production crawl covered 315 pages, but its frozen raw export retained only 35 pages and zero links. That could not prove current-code evaluation against the complete real input. The approved remedy was one new polite crawl plus a versioned, credential-free, runner-native replay artifact.

Before the crawl, the replay feature was implemented with TDD, independently reviewed, committed as `beb8e31`, normally pushed, and both push and PR CI checks passed.

## 4. Target and request-scoped safety envelope

- Target: `https://www.baolaipackaging.com/`
- `total_max_pages=1000`
- `chunk_target_pages=25`
- `politeness="polite"`
- `fill_sitemap_orphans=true`
- `sitemap_fill_cap=500`

These values were used only for this acceptance session. They were not written into system defaults, the Rule Engine, or permanent Master Audit limits.

## 5. Crawl identity, coverage, and runtime

- Session: `c807ebd6a1bf4e63`
- Upstream crawl ID: `6`
- Status: `done`
- Main crawl pages reported before sitemap fill: 42
- Main export records before sitemap fill: 47
- Sitemap-only candidates attempted: 268
- Sitemap-only candidates successfully filled: 268
- Final unique pages: 315
- Final per-page artifact rows: 315 unique URLs
- HTTP status distribution in the final per-page artifact: 315 x 200
- Sitemap coverage: 100.0%
- Final session pages: 315
- Main crawl finalization runtime: 217 seconds
- End-to-end session runtime: 587 seconds
- Chunk error rate: 0.0%
- Final polite delay: 500 ms

No crawl trap, faceted/query/session explosion, calendar loop, 429 surge, or production 5xx surge was observed. The crawl completed naturally below 1,000 pages. Truncation status is `NOT_TRUNCATED`; `CRAWL_TRUNCATED_BY_ACCEPTANCE_SAFETY_LIMIT` does not apply.

The persisted upstream graph contains 2,753 link rows from the main crawl. A trustworthy complete post-fill link count is unavailable because the full replay artifact failed before registration; this is part of the merge blocker and is not inferred from derived reports.

## 6. Request and error summary

- Sitemap fill: 268 attempted, 268 successful, 0 broken, cap not hit.
- External link smoke: 81 targets; 77 OK, 2 OK after redirect, 1 timeout, 1 forbidden.
- Content audit: 315 pages.
- Extended checks: 3,125 findings.
- No retry storm, rate-limit bypass, aggressive concurrency, or duplicate crawl start occurred.

## 7. Replay artifact result

Required filename pattern: `<domain>-<timestamp>.audit-replay-v1.json.gz`.

- Registration result: `FAIL`
- Event: `v3_artifact_failed`
- Error type: `ReplayValidationError`
- Partial marker: `v3_artifacts_partial`
- Invalid file registered: no
- Invalid file retained: no
- Replay pages: unavailable
- Replay links: unavailable
- Replay SHA-256: unavailable
- Crawl/replay page parity: not proven

The first failure event only recorded the exception type, not the fixed contract reason. Investigation against the preserved real SQLite data reproduced the failure: one real page meta description contains the ordinary phrase “basic information,” while the scanner treated every `Basic <word>` phrase as HTTP Basic authentication. The old scanner flagged six real database fields; after the minimal fix, the same frozen database produces zero credential-like matches. A real-string regression fixture now passes, and controlled `ReplayValidationError` events record a safe reason.

Because the replay was deleted before the fix and the sitemap-filled raw page objects were not otherwise serialized, generating a replacement 315-page replay from CSV/PDF/snapshot data would fabricate missing inputs. No replacement was fabricated.

### Merge-final blocker root-cause closure (offline)

The replay failure has now been root-caused without another production request. The crawl ran at `beb8e31`, whose credential scanner matched any whitespace-delimited `Basic <word>` sequence. Ordinary real page copy therefore triggered `ReplayValidationError("credential-like replay data detected")`. At that HEAD the event intentionally exposed only the exception type, so the preserved event is `v3_artifact_failed` without a reason. The writer then deleted the invalid gzip and did not register it. This was not a page-count, duplicate-URL, cleanup-order, generator, or serialization-timing failure.

The replay lifecycle is correctly located after sitemap fill, final sitemap reconciliation, and crawl-completeness construction, while the complete normalized `pages`, `links`, `site_data`, reconciliation, and provider cache are still live, and before artifact registration, packaging, or cleanup. The serializer now performs write, read-back validation, and explicit semantic parity before registration and logs `REPLAY_PARITY_PASS` with page count, link count, and SHA-256.

An independent link-lifecycle defect was found in the export boundary: direct `{pages, links}` responses returned pages but silently discarded the top-level links list. The preserved upstream database proves crawl 6 retained 47 main-crawl pages and 2,753 distinct source/target link rows; sitemap fill then added 268 page records with per-page link details. The parser now materializes the top-level link list once, and replay normalization combines it with per-page link details without consuming an iterator twice.

Rule 1's false Critical was caused by `_site_check()` flattening every robots.txt User-agent group into one `Disallow` list. Nine unrelated bot-specific `Disallow: /` directives consequently appeared to block all search crawlers. The offline contract now retains User-agent groups and only produces an important-path finding with the applicable agent, blocked path, robots response status, expected value, data source, confidence, remediation, and acceptance criteria. Missing Sitemap declarations are evaluated only when that field was actually collected; unknown legacy evidence is not converted to FAIL.

Rule 6 was not loaded from an old ZIP or directory glob. Its delivered row was generated by the crawl HEAD before the redirect normalization fix. The remaining provenance risk was minute-level shared filenames without a same-run manifest. Finalization now writes an additive `artifact-manifest.json` containing session ID, source URL, current Git HEAD, generation time, artifact kind/name, and SHA-256. ZIP construction accepts only the current session registry, verifies every registered file against that manifest, and refuses partial bundles missing replay or another required Master artifact.

The mandatory synthetic gate now passes with 315 pages and 1,260 non-zero internal-link records: original references are cleared, replay is loaded, URL/status/canonical/robots/title/description/H1/hreflang/schema/depth/word-count/redirect/sitemap/link parity passes, RuleRunner produces exactly 80 coverage rows, and the provenance-verified ZIP has valid CRC with no stale file. Status: `OFFLINE_FINAL_BUNDLE_PASS`. This does not change the overall decision; a final real current-HEAD acceptance crawl and CI gate are still required.

## 8. Preserved frozen evidence

No cleanup ZIP was requested, so session/upstream rows remain available. Before any cleanup, the following local ignored evidence was preserved under `reports/production-acceptance-c807ebd6a1bf4e63/`:

- `librecrawl-state.db` - 40,960 bytes
- `librecrawl-users.db` - 4,759,552 bytes
- `www.baolaipackaging.com-20260809-0654.audit-snapshot-v1.json.gz` - 75,658 bytes
- Snapshot SHA-256: `24e312063b0e751bea92d4bb5016678bf97193a0a856e09ee9867d1f1055af6b`

These files are diagnostic/frozen evidence, not a substitute for the missing replay contract.

## 9. 80-rule coverage

`coverage.csv` parses as UTF-8 CSV with exactly 80 unique audit IDs, exactly IDs 1..80:

- `EXECUTED_FULL`: 42
- `EXECUTED_PARTIAL`: 1
- `NOT_CHECKED`: 27
- `NOT_APPLICABLE`: 10
- `PASS`: 29
- `FAIL`: 5
- `WARNING`: 3
- `OPPORTUNITY`: 6
- `UNKNOWN`: 37

No `NOT_CHECKED` or `NOT_APPLICABLE` row is reported as PASS. Provider absence remains a missing-source state rather than an SEO failure. The one partial row confirms the corrected partial-coverage contract executed in production.

Coverage SHA-256: `fd1f34b45bd468f7de5dd63919fe23145ffda1962966ac9f160ae5183bc8b87f`.

## 10. Previous 53 confirmed false positives

The prior 53 confirmed systemic false positives were distributed across Rules 1, 6, 11, 25, and 45.

Production artifact comparison gives:

- Resolved in the new crawl artifact: 37
- Remaining systemic false positives in the new crawl artifact: 2
- Reclassified as evidence-backed real zero-inbound issues: 14
- Total: 53

The 14 reclassifications are Rule 11 URLs whose new snapshot evidence reports zero inbound links. Rules 25 and 45 no longer reproduce. Thirty-five prior Rule 11 false rows no longer reproduce.

The two remaining artifact defects are:

1. Rule 6 mapped production `alt_redirects_properly=true` directly into a legacy problem flag. Legacy output from the same run reported both HTTPS and www redirects as correct. The context-boundary normalization was fixed in `f4fb12c`; full regression and CI are green, but the production artifact still contains the old false Critical row.
2. Rule 1 reports nine duplicate `Disallow: /` paths without retaining User-Agent association. That is insufficient evidence to claim a global Critical block and still requires an agent-aware fixture/data-contract decision. It was not hidden or heuristically removed.

After the Rule 6 code fix, code-level disposition is 38 resolved, 1 remaining insufficient-evidence/systemic item, and 14 reclassified real. Artifact-level disposition remains 37/2/14 because exact offline replay is unavailable.

## 11. P0/P1 human review

The new task artifact contains 8 Critical/P0 rows and 72 High/P1 rows.

Critical rows:

- Rule 1: one insufficient-evidence/systemic robots finding; blocker.
- Rule 6: one confirmed systemic false positive; fixed after the crawl but still present in the artifact.
- Rule 19: five PSI lab/field-data records; three are opportunities and two explicitly state that absent CrUX data is not a confirmed PASS.
- Rule 67: one informational “no staging URL found” record, explicitly not proof that no staging site exists.

High rows:

- Rule 11: 15 zero-inbound candidates backed by the new snapshot graph summary.
- Rule 13: 44 title-width/uniqueness findings.
- Rule 17: one near-duplicate candidate.
- Rule 20: four Lighthouse proxy opportunities explicitly labeled as not real TTFB/log evidence.
- Rule 24: four simulated-mobile opportunities.
- Rule 61: four field-vs-lab informational records.

The human review therefore does not pass the merge gate: confirmed/insufficient-evidence systemic rows remain in the delivered P0 set. Real site findings were not removed or downgraded to make acceptance pass.

## 12. Tasks

`master-audit-tasks.csv` contains 894 open rows:

- Priority: 8 Critical, 72 High, 813 Medium, 1 Low
- Severity: 342 Error, 359 Warning, 92 Opportunity, 101 Info

The artifact retains affected URLs, evidence, priority, severity, remediation, owner, acceptance criteria, and confidence. It is structurally usable, but it is not final because the two known P0 systemic rows remain.

Tasks SHA-256: `8af39a37e7eb5ce37610eba40d3e6b72bd5e95fa98201656b386faf28e041f67`.

## 13. Manual review

The runner’s formal artifact is `manual-review.md` (not CSV). It contains all eight manual rules: 53, 54, 55, 56, 57, 71, 72, and 73. Every entry retains required evidence, review instructions, acceptance criteria, PENDING/IN_REVIEW/final status choices, evidence, notes, reviewer, and timestamp fields. No manual PASS was fabricated.

Manual review SHA-256: `a1b59362d4253e5d350427ae403e96ef153f8736a314ebe4b5184ce8ec0fed68`.

## 14. Score, coverage, and confidence

- Audit Score: 81.37 / 100
- Coverage: 61.43%
- Finding confidence: 97.09% (High)
- Eligible rules: 70
- Executed rules: 43
- Not checked: 27
- Not applicable: 10

The score separates quality, coverage, and confidence. Missing providers are excluded rather than counted as PASS. Score JSON SHA-256: `8607e1827b047764c52d5ceed57fbdf94d8bc5ff8cd9cb546e3fd43dfab8a35c`.

Exact post-fix deterministic rerun against the same full input cannot be performed because the replay artifact is missing. Unit/regression fixtures continue to verify deterministic scoring.

## 15. PSI and other providers

PSI ran on exactly five representative URLs, mobile only, through the shared provider cache:

- 4 successful normalized snapshots
- 1 timeout (`PSI request timed out after 30s`)
- No full-site PSI execution

`performance.csv` contains five mobile rows and has SHA-256 `9dbcc727307b13c95ca0f56d9d3154dac9996a1eb531185f81dbd13b89bca685`.

No credentials/data were supplied for GSC, Semrush, GA4, server logs, WordPress privileged, rendered DOM, or availability monitoring. They remain `NOT_CHECKED` / `LIVE_VALIDATION_PENDING`; no mock evidence was inserted.

## 16. Snapshot and controlled diff

- Production Snapshot A: schema v1, 315 pages, 315 indexable pages, gzip-valid.
- Controlled synthetic Snapshot B: 315 pages, explicitly named `CONTROLLED-SYNTHETIC-B`; it is test-only and not production evidence.
- Controlled diff: 3 rows - one `TITLE_CHANGED/INFORMATIONAL_CHANGE`, one `INDEXABILITY_CHANGED/REGRESSED`, and one `STATUS_CHANGED/REGRESSED`.

The snapshot/diff engine passes this controlled validation. The synthetic B data was not fed into production findings, coverage, tasks, score, Markdown, or PDF.

## 17. Markdown and PDF validation

Generated real documents:

- Master Markdown: 13,369 bytes; SHA-256 `c417e0ce3e77fd72e59356262a1c86c5a982156e1cd98d71e54f0809753b1f85`
- Master PDF: 177,697 bytes; 9 A4 pages; SHA-256 `8fab5a755c914418f1d449584e821dbeb818a44bba16bda0bb09d9f4efbe9d41`
- Legacy Markdown: 72,562 bytes; SHA-256 `d3330e87b28119ae6c729e82fa8fd1e94b8ffe18ed380c9f1745964d45fa634e`
- Legacy PDF: 232,500 bytes; 45 A4 pages; SHA-256 `8d1e9fd67a1bcc91c7b426016fcc200bca47578d29974898fbd05b7c6f07c543`

Both PDFs are valid, unencrypted WeasyPrint 69.0 PDF 1.7 files. All pages were rendered to PNG contact sheets for visual inspection. The Master PDF has readable Chinese acceptance criteria, stable headers/footers, no clipping, and no blank pages. The legacy PDF is readable and complete; a decorative unsupported glyph appears as a box in the final checklist heading, but substantive text and tables remain usable.

PDF structural/visual validation passes, but the Master PDF is not merge-final because it still contains the two known systemic P0 rows.

## 18. ZIP result

- Final post-fix ZIP: not generated
- ZIP size: unavailable
- ZIP SHA-256: unavailable
- ZIP integrity/CRC: not applicable

This is intentional fail-closed behavior. The replay artifact was invalid, so calling `librecrawl_audit_zip(..., auto_cleanup=true)` would have produced a seemingly complete bundle and removed evidence needed for diagnosis. No cleanup was performed.

## 19. Secret and credential scan

PASS for the 19 current-session report/frozen-evidence files scanned. The real PageSpeed key has zero byte matches. No GitHub token, bearer JWT, private-key marker, OAuth token, cookie/session credential, or fabricated provider credential was found.

Tracked non-test source also passes the credential-pattern scan. The replay serializer retains only its fixed safe response-header allowlist and rejects credential-bearing query/fragment/signed URLs.

## 20. Regression, integrity, and benchmark

Fresh local validation on supported Python 3.12:

- 771 tests passed
- 0 failed
- 0 skipped
- 1 warning (existing `datetime.utcnow()` deprecation)
- Test runtime: 2.30 seconds
- Python compile: PASS
- Rule registry: exactly 80 unique IDs, IDs 1..80
- JSON validation: PASS
- `docker compose config --quiet`: PASS
- `git diff --check`: PASS
- Production Docker artifact smoke: 80 coverage rows, valid replay, PDF, and ZIP with providers disabled

Fresh replay serialization benchmark:

- 100 pages: 0.006 seconds, 0.002 MiB
- 1,000 pages: 0.050 seconds, 0.012 MiB
- 5,000 pages: 0.249 seconds, 0.057 MiB

The benchmark uses compact synthetic inputs and verifies write-read-validation/page parity; it does not impose a system page cap.

## 21. GitHub CI

PASS. Both push and Draft PR `Offline validation (Python 3.12)` checks are green for:

- `beb8e31` replay feature
- `a021cfb` credential false-positive fix
- `f4fb12c` redirect evidence normalization
- `acac52a` authorization-value validation hardening

The final report commit `02e5e81` also passed both checks (push and Draft PR #1, completed 2026-08-09T08:14Z). PR #1 remains Draft.

## 22. Merge-gate evaluation

- One current-code real crawl completed naturally: PASS
- Complete replay safely preserved: FAIL
- Crawl/replay page parity: FAIL / unavailable
- Full final artifact package from final HEAD: FAIL
- Coverage exactly 80 rows: PASS
- Previous 53 false positives dispositioned: PASS, but one insufficient-evidence/systemic item remains
- No blocking systemic P0/P1: FAIL
- Tasks structurally usable: PASS, but not merge-final
- Manual workflow valid: PASS
- Score/coverage/confidence semantics: PASS
- PDF structurally valid: PASS, but not merge-final
- Final ZIP valid: FAIL / not generated
- Snapshot/diff engine: PASS
- No fabricated provider evidence: PASS
- Secret scan: PASS
- Fresh full regression: PASS
- GitHub CI: PASS including the final report commit `02e5e81`

The only honest final result is:

`NOT_READY_TO_MERGE`

Do not merge Draft PR #1. A future acceptance decision requires either a user-approved new acquisition run after the remaining robots evidence contract is resolved, or another authorized method that preserves the complete normalized input without revisiting the production site.

## 23. Post-report verification addendum (2026-08-09)

Recorded after the report above was committed:

- The Rule 1 robots evidence contract is now resolved in code: `_parse_robots_txt` retains User-agent groups, bot-specific `Disallow` rules no longer flatten into a global block, and findings carry `applicable_agents`, blocked paths, robots status, expected value, data source, confidence, remediation, and acceptance criteria. Covered by `tests/phase12/test_rule1_evidence_contract.py` (committed in `02e5e81`).
- The final report commit `02e5e81` passed both GitHub Actions `Offline validation (Python 3.12)` checks (push and Draft PR #1).
- Fresh full regression at `02e5e81`: 771 passed, 0 failed, 0 skipped.
- Server compile, 80-rule registry integrity, provider/adapter/tool integrity, tracked JSON parsing, and Compose config validation: PASS.
- Secret/credential scan of tracked source and current-session report artifacts: PASS.

The overall decision remains `NOT_READY_TO_MERGE` because the production artifact was generated at `beb8e31` and cannot be regenerated without either a new user-approved acquisition run or another authorized method that preserves the complete normalized input. The remaining external live validations (GSC, Semrush, GA4, server logs, WordPress, rendered DOM, availability) still require user-supplied credentials or inputs.
