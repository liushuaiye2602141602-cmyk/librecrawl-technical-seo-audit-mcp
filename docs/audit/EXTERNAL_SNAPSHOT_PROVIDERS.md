# External Evidence Snapshot Providers

## Status

The schemas, privacy validation, providers, Rules 46/48/80, and integration are
fixture-validated. Real browser and monitoring exports remain input-dependent.
Missing or invalid inputs leave the rules `NOT_CHECKED`; they never create a
synthetic PASS.

Both files are limited to 5 MiB, must match the audited host, are age-bound, and
reject secrets, identities, raw HTML/text, screenshots, cookies, headers, and
form values.

## Rendered DOM summary

```json
{
  "schema_version": "render-audit-v1",
  "collected_at": "2026-08-09T07:00:00+00:00",
  "site_url": "https://example.com",
  "pages": [{
    "url": "https://example.com/products",
    "raw_text_chars": 1200,
    "rendered_text_chars": 1800,
    "raw_internal_links": 20,
    "rendered_internal_links": 28,
    "initial_items": 12,
    "after_scroll_items": 36,
    "load_more_requires_interaction": true,
    "crawlable_pagination_fallback": false,
    "lazy_images_without_fallback": 2
  }]
}
```

An external Playwright/Puppeteer/browser collector may produce this summary,
but must discard DOM content before handoff. Rule 46 checks material render-only
text and links. Rule 48 checks interaction-only collections without crawlable
pagination and lazy images without static fallback. Both remain partial because
the snapshot is capped at 500 pages.

## Availability monitoring summary

```json
{
  "schema_version": "availability-monitor-v1",
  "collected_at": "2026-08-09T07:00:00+00:00",
  "site_url": "https://example.com",
  "window_hours": 168,
  "endpoints": [{
    "url": "https://example.com/",
    "total_checks": 2016,
    "failed_checks": 2,
    "five_xx_checks": 1,
    "availability_pct": 99.9,
    "p95_ms": 900,
    "locations": 3
  }]
}
```

Any monitoring system can export this aggregate. Rule 80 reports observed 5xx,
availability below 99.9%, and p95 latency above 3000 ms. A PASS is full only
with at least 168 hours and two locations; smaller evidence is partial.
