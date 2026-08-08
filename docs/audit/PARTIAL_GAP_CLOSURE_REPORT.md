# Existing-partial crawl gap closure report

**Date:** 2026-08-09

**Verification:** 540 passed, 0 failed, 0 skipped

## Delivered

All seven `EXISTING_PARTIAL` rules that previously had no adapter are now
bound, bringing the compatibility harness from 48 to 55 adapters:

- Rule 2: sitemap existence, count, HTTP status, noindex, and canonical health.
- Rule 5: session, future-calendar, internal-search, faceted, and high-parameter
  crawl-space patterns.
- Rule 13: missing/duplicate titles and conservative pixel-width estimation.
- Rule 23: case-insensitive Cache-Control and exported cache/CDN header checks.
- Rule 25: HTTP coverage, mixed resources, and optional TLS validity/expiry
  evidence.
- Rule 40: actionable, formula-safe task CSV with assignee, due date, status,
  verification, remediation, and acceptance fields.
- Rule 66: public caching of WordPress cart, checkout, login, account, and form
  paths.

## Execution truth

Coverage now consumes exact harness execution facts. An absent adapter, adapter
exception, or missing required evidence becomes `NOT_CHECKED + UNKNOWN` rather
than a fabricated PASS. Checks can also preserve findings while declaring
partial evidence; partial response-header exports now produce
`EXECUTED_PARTIAL` with a specific coverage reason.

The seven rules remain `EXISTING_PARTIAL`: GSC/Bing submission, crawl logs,
search intent/CTR, static-resource headers, production TLS evidence, project
management APIs, and WordPress configuration-level evidence are not claimed.

## Safety and compatibility

- No check performs new HTTP requests.
- Spreadsheet formula prefixes are neutralized in task CSV cells.
- Adapter exception details are reduced to exception class names.
- Existing MCP signatures and legacy artifacts remain unchanged.
- All 33 partial registry rules now have registered adapters.
