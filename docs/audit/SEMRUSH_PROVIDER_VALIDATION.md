# Semrush provider validation

Status: `IMPLEMENTED_OFFLINE / LIVE_VALIDATION_PENDING`

The V3 runner now registers a credential-safe Semrush Backlinks API v4 provider. It collects the root-domain overview and a bounded, Authority Score-ordered list of lost links. Identical requests are cached for the audit session; partial family success is preserved; all-error runs remove `Semrush API` from available sources.

Rules 31 and 77 are executable. Rule 31 records an auditable backlink baseline. Rule 77 reports lost followed links from source domains with Authority Score at least 30 when they target crawled 200 URLs, and marks truncated results as partial.

Offline validation covers v4 headers, parameters, caching, response validation, sanitized failures, configuration, target resolution, partial/all-error behavior, runner registration, checks, and source-of-truth migration. Full regression: 587 passed.

Live validation requires a paid Semrush v4 API key and remains pending. The v4 Backlinks API is currently described by Semrush as Early Access: [official Backlinks API v4 reference](https://developer.semrush.com/api/v4/seo/backlinks/).
