# Audit Replay V1 Design

**Date:** 2026-08-09

**Status:** Approved by the user's final Scheme A specification

**Repository baseline:** `30d1c7e` on `feat/master-audit-completion`

## Objective

Add a runner-native, versioned `<domain>-<timestamp>.audit-replay-v1.json.gz` artifact that preserves the complete credential-free inputs used by a V3 audit. A validated artifact must support offline re-execution of crawl-backed rule evaluation, findings, coverage, task generation, manual-review template generation, audit scoring, reports, snapshots, and packaging without contacting the audited site.

The artifact is additive and exists only when Master Audit V3 is enabled. Feature-flag-off behavior and every legacy artifact remain unchanged.

## Architecture and Data Flow

The finalizer continues its existing acquisition and sitemap-fill flow. After it has the final merged `pages`, `links`, `site_data`, `sitemap_reconciliation`, and `crawl_completeness`, the V3 path runs providers and rule evaluation. It then builds one replay document from those exact final inputs plus safe normalized provider evidence, writes deterministic UTF-8 JSON through gzip, immediately reloads it, validates the contract, and only then registers it with `state.add_artifact`.

The implementation lives in a focused `audit_rules/replay.py` module. `runner.py` only supplies current-run inputs, records validation failures through the existing V3 partial-artifact event path, and registers a successfully validated file. The ZIP builder already packages every registered artifact, so it requires no special replay branch.

## Replay Schema V1

The top-level object is:

```json
{
  "schema_version": "1.0",
  "artifact_type": "audit_replay",
  "generated_at": "ISO-8601 UTC",
  "source_url": "https://example.com/",
  "git_head": "40-character commit id or empty when unavailable",
  "crawl_metadata": {},
  "counts": {"pages": 0, "links": 0},
  "pages": [],
  "links": [],
  "site_data": {},
  "sitemap_reconciliation": {},
  "crawl_completeness": {},
  "provider_evidence": {}
}
```

`REPLAY_SCHEMA_V1` defines required top-level fields and the explicit normalized page/link fields required by current adapters, checks, contexts, snapshots, and report generation. Page records preserve the current `EXPORT_FIELDS` family and sitemap-fill `source`, plus safe response headers when present. Link records preserve source, target, anchor, relationship, internal/external classification, status, and redirect/error fields used by link-graph consumers. Site data preserves the normalized robots, sitemap, redirect, and TLS evidence consumed by current rules. Reconciliation and completeness preserve their current project field names.

Raw HTML, request headers, cookies, authorization data, local paths, and arbitrary unknown fields are outside the v1 contract. Missing fields remain absent or empty; the serializer never refetches the target to fill them.

`crawl_metadata` records the session's start/completion times, upstream crawl ID, the request-scoped crawl parameters, politeness, sitemap-fill settings/result, truncation status, and current build identity. The acceptance limits remain run metadata, not system defaults or Rule Engine limits.

## Safe Response Headers

`sanitize_response_headers(headers)` is allowlist-only and case-insensitive. It retains only normalized values for:

- `X-Robots-Tag`
- `Cache-Control`
- `Age`
- `ETag`
- `Last-Modified`
- `Content-Type`
- `Content-Language`
- `Link`
- `Strict-Transport-Security`
- `Content-Security-Policy`
- `X-Frame-Options`
- `X-Content-Type-Options`
- `Referrer-Policy`

It excludes `Authorization`, `Proxy-Authorization`, `Cookie`, `Set-Cookie`, `WWW-Authenticate`, API-key headers, bearer/session/token headers, and every custom header not on the allowlist. Header values are JSON-safe strings or stable string lists. No HTTP request is made to obtain missing headers.

## Provider Evidence

Raw provider HTTP responses are never stored. `provider_evidence` contains only normalized, credential-free evidence already used by the current audit.

For PageSpeed it may contain the strategy, collection status/time, and stable URL-sorted `PerformanceSnapshot` fields from the current audit cache. It never contains an API key, request authorization, cookies, or raw credential-bearing request/response data.

GSC, Semrush, GA4, server logs, and WordPress privileged sources record an explicit status such as `NOT_CHECKED`, `UNAVAILABLE`, or `LIVE_VALIDATION_PENDING` when no real normalized evidence was collected. Mock or synthetic provider evidence is forbidden.

## Determinism and Integrity

Pages sort by normalized URL. Links sort by source URL, target URL, anchor, and relationship. Provider snapshots sort by strategy and URL. JSON uses UTF-8, stable key ordering, compact stable separators, and gzip with deterministic payload ordering. `generated_at` may differ between runs; no random identifier is added.

The file SHA-256 is calculated externally after writing and is not embedded in the file. Production Acceptance records the filename, byte size, hash, page count, and link count.

## Validation Contract

The writer must immediately call the loader and validator. Validation requires:

- supported `schema_version` and `artifact_type`;
- matching expected `source_url`;
- every required top-level collection/object;
- `counts.pages == len(pages)` and `counts.links == len(links)`;
- non-empty, unique page URLs with stable ordering;
- `crawl_completeness.pages_crawled == len(pages)` for completed production crawls;
- required crawl metadata and current rule input collections;
- no credential-like key or secret marker in the decoded document.

Production Acceptance additionally compares the session's completed page count to the replay count. A mismatch produces `REPLAY_ARTIFACT_INCOMPLETE` and fails the merge gate.

## Failure Semantics

Serialization, writing, reloading, or validation failure does not delete crawl data or suppress other recoverable outputs. The runner records `v3_artifact_failed` and `v3_artifacts_partial` with the replay artifact kind and a sanitized error type/reason. It does not register an invalid replay file. Consequently the ZIP cannot appear replay-complete, and Production Acceptance remains `NOT_READY_TO_MERGE`.

## Offline Replay Contract

The loader returns the validated replay document. `replay_pipeline_inputs()` maps it back to the current `export_data` and `existing_data` shapes without network I/O. A full-pipeline test writes a known crawl fixture, clears the original structures, reloads the artifact, runs the RuleRunner/report pipeline, asserts exactly 80 coverage rows, and compares representative crawl-dependent findings with the direct-input path. This proves audit replay rather than JSON round-trip only.

Snapshot B remains explicitly synthetic diff-test data and is never included as production provider or crawl evidence.

## Test Strategy

TDD covers:

1. Safe-header retention and removal of authorization/cookie/API-key secrets.
2. Deterministic write/load validation, ordering, counts, supported schema, unique URLs, and completed-page parity.
3. Offline RuleRunner/report replay with 80 coverage rows and semantically identical representative findings.
4. Normalized real-provider evidence and explicit pending statuses without mock evidence.
5. Runner V3-only registration, ZIP inclusion through the existing registry, and explicit partial failure events.
6. Full repository regression, Python compile, registry/JSON/Compose checks, security validation, and benchmark before the production crawl.

## Production Acceptance Sequence

After the feature commit is normally pushed and both Draft PR CI runs are green, run exactly one crawl of `https://www.baolaipackaging.com/` with `total_max_pages=1000`, `chunk_target_pages=25`, `politeness="polite"`, `fill_sitemap_orphans=true`, and `sitemap_fill_cap=500`. Before cleanup, require replay page parity and a passing replay validation. Then download the ZIP with `auto_cleanup=True`, save it locally, verify SHA-256/CRC/artifacts, and perform the approved false-positive, P0/P1, coverage, task, manual, score, PDF, snapshot/diff, secret, regression, benchmark, CI, and final merge-gate reviews. Draft PR #1 remains Draft and is never merged by this workflow.
