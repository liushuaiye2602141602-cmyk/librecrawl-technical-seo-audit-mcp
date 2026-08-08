# Google Search Console provider validation

Status: `IMPLEMENTED_OFFLINE / LIVE_VALIDATION_PENDING`

The V3 pipeline now registers `GSCDataProvider` under the canonical source name `GSC API` and compatibility alias `GSC`. It reads an OAuth bearer token and exact property identifier only from runtime configuration. No credential is stored in source, tests, error messages, or artifacts.

Implemented API contracts:

- Search Analytics `query`: page/query/country/device dimensions, finalized data, two comparable 28-day windows, 25,000-row pagination, 50,000-row configurable cap, and request caching.
- URL Inspection `index.inspect`: deterministic bounded crawl sample and indexed-version canonical evidence.
- Sitemaps `list`: submitted sitemap inventory.

Executable rules: 44, 52, 75, and 76. Provider-wide failure yields `NOT_CHECKED / UNKNOWN`; incomplete URL Inspection sampling yields `EXECUTED_PARTIAL`. Rule 72 remains manual because the public Search Console API does not expose Manual Actions or Security Issues.

Validation performed on 2026-08-09:

- MockTransport request/response contract, pagination, caching, property encoding, and sanitized 401/403/429/5xx/timeout/JSON failures.
- Provider configuration, comparable windows, sitemap collection, deterministic inspection sampling, partial success, all-error behavior, context enrichment, and runner registration.
- Four rule checks plus source-of-truth classification and coverage semantics.
- Full repository regression: 566 passed.

Live validation needs a user-authorized OAuth 2.0 token for a verified Search Console property. The supplied PageSpeed API key cannot authorize private Search Console data.

Official contracts: [Search Analytics query](https://developers.google.com/webmaster-tools/v1/searchanalytics/query), [URL Inspection inspect](https://developers.google.com/webmaster-tools/v1/urlInspection.index/inspect), [Sitemaps list](https://developers.google.com/webmaster-tools/v1/sitemaps/list), and [Search Console authorization](https://developers.google.com/webmaster-tools/v1/how-tos/authorizing).
