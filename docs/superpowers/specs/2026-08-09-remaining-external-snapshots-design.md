# Remaining External Snapshot Providers Design

## Goal

Close Rules 46, 48, and 80 without bundling a browser runtime or binding the
audit service to one uptime-monitor vendor. External collectors produce small,
privacy-safe JSON summaries; the audit service only validates and evaluates
them.

## Rendered DOM snapshot

`render-audit-v1` is enabled with `MASTER_AUDIT_RENDER_ENABLED=true` and
`JS_RENDER_AUDIT_PATH`. It contains a site URL, collection time, and at most 500
same-host page summaries. No HTML, visible text, cookies, headers, screenshots,
tokens, or form values are accepted.

Per-page fields are counts and booleans: raw/rendered text characters,
raw/rendered internal links, initial/after-scroll item counts, whether a
Load-More action is required, whether a crawlable pagination fallback exists,
and count of lazy images lacking a noscript/static fallback.

- Rule 46 flags material render-only text or links.
- Rule 48 flags content requiring interaction/scroll without crawlable fallback
  and lazy images without static fallback.
- Both stay partial because a bounded page sample cannot prove site-wide
  rendering behavior or Google indexing.

## Availability snapshot

`availability-monitor-v1` is enabled with
`MASTER_AUDIT_AVAILABILITY_ENABLED=true` and `AVAILABILITY_AUDIT_PATH`. It
contains same-host URL aggregates for a declared window: total checks, failures,
5xx checks, availability percentage, p95 response time, and location count.

Rule 80 flags any 5xx observations, availability below 99.9%, and p95 latency
above 3000 ms. Evidence is full only for a window of at least 168 hours with at
least two locations; smaller windows raise partial execution rather than PASS.

## Shared safety behavior

Both files are opt-in, capped at 5 MiB, host-bound, age-bound, fail closed on
malformed data, and reject secret/identity/raw-content field names recursively.
Missing or invalid evidence yields `NOT_CHECKED`, never PASS.
