# GA4 provider validation

Status: `IMPLEMENTED_OFFLINE / LIVE_VALIDATION_PENDING`

The V3 runner now registers a GA4 provider backed by the Google Analytics Admin and Data REST APIs. It reads property metadata, paginates configured key events, and queries finalized 28-day daily activity and event counts. API families fail independently and errors never include OAuth tokens or response bodies.

Rules 34 and 35 are executable with explicit partial semantics. Rule 34 checks accessible GSC/GA4 evidence, property trash state, and data continuity while leaving Bing and duplicate browser-tag detection manual. Rule 35 compares configured key events with observed counts while leaving GTM preview and end-to-end submissions manual.

Offline validation covers request contracts, OAuth headers, pagination, caching, report normalization, provider gates, partial/all-error behavior, runner registration, checks, and source-of-truth migration. Full regression: 605 passed.

Live validation needs an OAuth token authorized for the specified property and remains pending. Official references: [GA4 Data API](https://developers.google.com/analytics/devguides/reporting/data/v1/rest), [properties.get](https://developers.google.com/analytics/devguides/config/admin/v1/rest/v1beta/properties/get), and [keyEvents.list](https://developers.google.com/analytics/devguides/config/admin/v1/rest/v1beta/properties.keyEvents/list).
