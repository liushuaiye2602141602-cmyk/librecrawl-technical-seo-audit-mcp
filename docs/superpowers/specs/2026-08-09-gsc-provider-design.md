# Google Search Console provider design

## Outcome

Add a credential-safe, cache-aware Google Search Console provider to the V3 audit pipeline. The provider exposes Search Analytics, submitted sitemaps, and indexed-version URL Inspection evidence without turning missing credentials or API failures into SEO passes.

## API boundary

- Authentication: OAuth 2.0 bearer access token with the read-only Search Console scope.
- Search Analytics: `webmasters/v3/sites/{siteUrl}/searchAnalytics/query`, using bounded `rowLimit` and `startRow` pagination.
- Sitemaps: `webmasters/v3/sites/{siteUrl}/sitemaps`.
- URL Inspection: `v1/urlInspection/index:inspect`; only the indexed version is available.
- Manual actions/security issues remain manual (Rule 72); the public API does not expose that report.

## Runtime contract

`MASTER_AUDIT_GSC_ENABLED`, `GSC_ACCESS_TOKEN`, and `GSC_SITE_URL` configure the production provider. Optional limits bound rows and inspected URLs. Secrets are read from the process environment, never stored in artifacts, logs, errors, or cache keys.

The client returns normalized dictionaries and raises typed, sanitized exceptions. It pages Search Analytics deterministically, stops at an empty or short page, and keeps an in-memory request cache. HTTP 401/403, 429, 5xx, timeouts, invalid JSON, and malformed payloads retain only safe status/class information.

The provider collects two finalized Search Analytics windows, the submitted sitemap inventory, and a deterministic sample of crawl URLs for inspection. It enriches `PageContext.gsc_data` by exact URL and injects a site-level payload into shared adapter data. At least one successful API family is required before the source is advertised as available.

## Rule scope

The first executable GSC rules are:

- Rule 44: declared canonical versus Google-selected canonical.
- Rule 52: queries producing impressions on multiple pages.
- Rule 75: material device/country performance splits.
- Rule 76: pages or queries with a meaningful decline between comparable periods.

Rules 2, 5, 13, and 16 may consume GSC evidence later but retain their crawl adapters. Rules 34, 46, and 48 still need GA4 or rendered-page evidence and must not be claimed as complete. Rule 72 stays manual.

## Truthful failure semantics

Missing/disabled configuration, zero successful calls, and provider-wide auth/quota/network failures remove both `GSC API` and the compatibility alias `GSC` from available sources. Dependent rows become `NOT_CHECKED / UNKNOWN`. Partial URL Inspection results preserve successful findings and report partial execution rather than silently passing failed URLs.

## Validation

Tests cover request shapes, URL encoding, pagination, cache reuse, sanitization, configuration gates, runner registration, context enrichment, source aliases, four rule outcomes, and all-error coverage. Live validation remains pending until a property-authorized OAuth token is supplied.
