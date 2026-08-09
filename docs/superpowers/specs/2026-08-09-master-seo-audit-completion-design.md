# Master SEO Audit Completion Design

**Date:** 2026-08-09

**Status:** Approved by the user-provided takeover specification

**Repository baseline:** `9448066` on `feat/master-audit-foundation`; 457 tests pass

## Objective

Complete every code-level capability that can reasonably be implemented for the LibreCrawl-backed 80-rule Master SEO Audit System. Completion is governed by `docs/handoff/FINAL_DEFINITION_OF_DONE.md` as corrected by the newer takeover specification and by a repository-wide final gap audit. A phase, version label, roadmap checkpoint, or one green test run is not a stopping condition.

## Source-of-Truth Order

When sources disagree, use this order:

1. Current Git repository
2. `audit_specs` CSV files
3. Automated tests
4. Runtime Rule Registry
5. Implementation code
6. Current takeover specification
7. Handoff documents
8. Historical completion reports

The current takeover specification supersedes two stale handoff assumptions:

- External-data and genuinely manual rules do not become `EXISTING_FULL` merely to make a counter reach 80. Their terminal state must truthfully distinguish implemented external-provider support, manual review, not-applicable profiles, and runtime execution status.
- Rule 74 comparison uses exported, versioned snapshots that survive ephemeral audit sessions; it does not depend on two session IDs remaining available.

## Architecture

The system keeps the established pipeline:

`crawl once -> normalize once -> provider enrichment -> evaluate many rules -> coverage/tasks/artifacts/report`

Rule functions remain pure consumers of `RuleDefinition`, `SiteContext`, `PageContext`, and a shared data dictionary. They do not fetch pages. External I/O is isolated behind providers. Expensive provider results are cached once per audit and reused by every dependent rule.

The three status axes remain independent:

- `impl_status`: design-time implementation classification
- adapter registration: executable code binding
- `execution_status` / `result_status`: per-audit coverage and outcome

Missing credentials or provider failures yield `NOT_CHECKED` / `UNKNOWN`, never an SEO failure or fabricated pass.

## Workstream Decomposition

Each subsystem is designed, planned, implemented, tested, documented, and committed as an independently reviewable unit:

1. Rule 74 versioned snapshot and diff engine
2. PageSpeed live smoke validation and any parser/integration corrections
3. GSC provider and GSC-backed rule integrations
4. Semrush provider and backlink/ranking integrations
5. GA4 provider for audit-relevant evidence only
6. Streaming Apache/Nginx server-log provider and analysis
7. WordPress remote-observable and privileged read-only providers
8. Manual review workflow and artifact
9. Deterministic audit score with separate coverage and confidence
10. Remediation task aggregation and evidence preservation
11. Final report and artifact pipeline, including ZIP packaging
12. Aggregate MCP tools and backward compatibility
13. Configuration, Docker/deployment, and documentation
14. Performance benchmarks at 100, 1000, and 5000 synthetic pages
15. Repository-wide final gap audit, closure of in-scope P0/P1/P2 gaps, and final DoD verification

Provider work is implemented fully with offline mocks even when live credentials are unavailable. Live validation is performed only when authorized credentials/data exist and is otherwise recorded as `LIVE_VALIDATION_PENDING`.

## Rule 74 Snapshot/Diff Design

The first subsystem defines `audit-snapshot-v1.json.gz` as a portable artifact with:

- `schema_version`, creation metadata, domain/base URL, and normalized page records
- stable URL ordering and deterministic fingerprints
- validation on export and load
- a reader that accepts the current schema and rejects unsupported required major versions clearly
- no dependency on server session persistence

Each normalized page records URL, status, indexability, robots, title, meta description, H1, canonical, hreflang, schema fingerprint, content fingerprint, internal-link summary, and important technical signals available from the crawl export.

The diff engine compares snapshots by normalized URL and emits structured changes for:

- `URL_ADDED`, `URL_REMOVED`, `STATUS_CHANGED`, `INDEXABILITY_CHANGED`
- `ROBOTS_CHANGED`, `CANONICAL_CHANGED`, `TITLE_CHANGED`, `DESCRIPTION_CHANGED`, `H1_CHANGED`
- `HREFLANG_CHANGED`, `SCHEMA_CHANGED`, `CONTENT_CHANGED`, `INTERNAL_LINK_REGRESSION`

Each change is classified as `FIXED`, `REGRESSED`, `NEW_ISSUE`, `UNCHANGED`, or `INFORMATIONAL_CHANGE` using evidence-based state transitions. The `crawl-diff.csv` writer preserves before/after values and evidence. Rule 74 consumes a supplied diff result from the shared data dictionary; snapshot file I/O stays outside the check function.

## Error and Safety Semantics

- Corrupt or unsupported snapshots fail validation with a precise error and never silently compare partial data.
- Provider auth, quota, timeout, 5xx, malformed, or partial responses remain provider-status events; dependent rules do not fail the audited website.
- Audited sites are treated read-only. No brute force, credential guessing, exploit attempts, pingback abuse, destructive requests, mass DNS enumeration, or production writes are permitted.
- WordPress privileged access is read-only and must prove that mutating methods are unavailable.
- PSI and other costly APIs use bounded sampling, caching, timeouts, and shared snapshots.

## Testing and Commit Discipline

Every implementation unit follows TDD with positive, negative, false-positive, and missing-data cases. Provider units additionally cover authentication failure, timeout, rate limit, 5xx, partial response, malformed response, and missing fields using offline mocks.

After subsystem tests pass, the complete `tests/` suite must pass before its checkpoint commit. Commits use focused `feat:`, `fix:`, `test:`, `docs:`, or `refactor:` messages. Existing user-owned files, especially the untracked `.agents/` directory, are not staged.

## Completion Criteria

The project can be declared complete only when:

- all 80 rules exist exactly once and have truthful terminal implementation semantics;
- every reasonably automatable rule and every external provider architecture is implemented and wired;
- genuine manual rules have a complete review workflow;
- artifacts, aggregate MCP tools, reports, configuration, Docker/deployment, and documentation are complete and backward compatible;
- full tests, project-configured validation, security checks, and performance benchmarks pass;
- `docs/FINAL_GAP_AUDIT.md` has no remaining in-scope implementable P0/P1/P2 gap;
- `docs/FINAL_IMPLEMENTATION_REPORT.md` records completed and pending live validations;
- the only remaining items require real credentials, paid entitlement, production access, user-supplied data, or objective human judgment.
