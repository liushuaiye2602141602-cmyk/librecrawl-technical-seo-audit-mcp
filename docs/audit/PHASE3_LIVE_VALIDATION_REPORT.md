# PageSpeed Insights live validation report

**Date:** 2026-08-09

**Target:** `https://example.com/`

**Credential handling:** process-scoped environment only; the key was not
printed, logged, written to a file, added to an artifact, or committed.

## Live results

The canonical PSI client returned a successful mobile response with:

- four normalized score categories: performance, SEO, accessibility, and best
  practices;
- six lab metrics: FCP, LCP, TBT, CLS, Speed Index, and TTI;
- URL-scope field data;
- Lighthouse version 13.4.1.

The `PageSpeedDataProvider` conversion also succeeded: canonical provider name
`PageSpeed API`, one cached successful snapshot, six populated lab metrics, and
the configured one-URL/mobile sampling boundary.

The full V3 pipeline then produced exactly 80 coverage rows, populated the
shared PSI cache once, executed Rule 19 without a missing-provider reason, and
generated the coverage CSV. This validates client → provider → runner → rules →
coverage data flow.

## Defects found and closed

1. The production integration runner did not register `PageSpeedDataProvider`.
2. Provider name `PageSpeedInsights` did not match registry source
   `PageSpeed API`.
3. An all-error PSI sample could leave the provider available and produce an
   apparent PASS instead of `NOT_CHECKED + UNKNOWN`.
4. Invalid PSI environment values could fail imports or accept unsupported
   strategies.
5. HTTP error bodies could be reflected into diagnostics and potentially expose
   request credentials.

## Automated verification

- Mocked missing-key, invalid-strategy, 400, 429, 5xx, timeout, malformed JSON,
  and successful normalization tests.
- Provider registration, canonical naming, safe configuration, all-error, and
  mixed-success coverage tests.
- Existing sampling and API-call deduplication tests remain green.
- Full suite: 514 passed, 0 failed, 0 skipped on Python 3.14.5.
