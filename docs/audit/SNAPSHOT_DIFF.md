# Portable crawl snapshots and Rule 74

Rule 74 compares two portable, versioned crawl snapshots. It does not depend on
an audit session ID or on server-side audit history.

## Workflow

```text
Audit A -> save *.audit-snapshot-v1.json.gz as the baseline
deploy or change the site
Audit B + baseline -> current snapshot + crawl-diff.csv + Rule 74 findings
```

Set `MASTER_AUDIT_V3_ENABLED=true` to enable the 80-rule shadow pipeline. To
compare a later crawl, set `AUDIT_SNAPSHOT_BASELINE_PATH` to the earlier gzip
snapshot. `AUDIT_SNAPSHOT_OUTPUT_DIR` optionally selects a persistent output
directory; otherwise artifacts are written to `REPORTS_DIR`.

In containers, mount the baseline and output directory on persistent storage.
The application never searches historical sessions or guesses a baseline.

## Snapshot contract

The artifact is deterministic gzip-compressed UTF-8 JSON with
`schema_version: 1`. Its root records the creation time, normalized base URL,
site profile, pages, and summary counts. Each page records:

- URL, HTTP status, indexability, robots, title, description, H1, canonical,
  and normalized hreflang entries;
- SHA-256 schema and content fingerprints;
- internal-link counts and target fingerprint;
- language, viewport, word count, and response time signals.

Readers accept additive fields in version 1 and reject unsupported schema
versions, missing required fields, invalid types, and duplicate URLs. Gzip
metadata uses a zero modification time so equal snapshots produce equal bytes.

## Difference contract

Comparison is URL-indexed and O(n) in the number of pages plus emitted changes.
`crawl-diff.csv` has exactly these columns:

```text
url,change_type,classification,field,before,after,evidence
```

It detects added/removed URLs; status, indexability, robots, canonical, title,
description, H1, hreflang, schema, and content changes; and material internal
link regressions. Classifications are `REGRESSED`, `NEW_ISSUE`, `FIXED`,
`INFORMATIONAL_CHANGE`, or optional `UNCHANGED`.

## Honest first-audit semantics

No baseline means Rule 74 is `NOT_CHECKED + UNKNOWN`, not PASS. A valid baseline
with no changes is distinguishable: the diff CSV contains its header, Rule 74
executes, and it may truthfully PASS. A corrupt or unsupported baseline logs
`snapshot_diff_failed`, does not make the provider available, and does not stop
legacy report generation; the current snapshot is still retained when it can
be built.

## Python interfaces

- `audit_rules.snapshot.build_snapshot_from_export()`
- `audit_rules.snapshot.snapshot_to_gzip_bytes()` / `snapshot_from_gzip_bytes()`
- `audit_rules.snapshot.write_snapshot()` / `load_snapshot()`
- `audit_rules.snapshot_diff.diff_snapshots()`
- `audit_rules.snapshot_diff.crawl_diff_csv_to_string()`
- `audit_rules.integration.build_snapshot_artifacts()`
