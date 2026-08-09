# Semrush provider design

## Outcome

Add a bounded optional Semrush provider for backlink inventory, lost-link evidence, referring domains, domain keyword positions and changes, and relevant organic competitor context. The provider must never leak API keys or consume units more than once for identical audit requests.

## API boundary

- `GET /apis/v4/backlinks/v1/overview` for aggregate backlink, referring-domain, new/lost, follow, and Authority Score metrics.
- `GET /apis/v4/backlinks/v1/links` with `is_lost = true`, explicit fields, Authority Score ordering, and a bounded result limit.
- `GET /apis/v4/backlinks/v1/ref-domains` for bounded referring-domain evidence.
- Standard Analytics `domain_organic` for keyword, URL, current/previous position, position change, volume, and traffic evidence.
- Standard Analytics `domain_organic_organic` for relevant organic competitor context.
- V4 authentication uses `Authorization: Apikey ...`; Standard Analytics uses the official TLS query-key contract. Keys remain process-only and are excluded from cache keys and errors.
- The v4 API is early access, so response validation and typed failures isolate contract drift.

## Runtime and truth semantics

`MASTER_AUDIT_SEMRUSH_ENABLED`, `SEMRUSH_API_KEY`, `SEMRUSH_TARGET`, `SEMRUSH_LOST_LINK_LIMIT`, `SEMRUSH_REFERRING_DOMAIN_LIMIT`, `SEMRUSH_DATABASE`, `SEMRUSH_KEYWORD_LIMIT`, and `SEMRUSH_COMPETITOR_LIMIT` configure the provider. The target defaults to the audit base URL when not explicitly configured. Identical requests use a session cache and paid row counts are bounded to 500 per report.

All API families are attempted independently. A successful family is preserved when another fails. Zero successful families remove `Semrush API` from available sources. Exceptions contain only status and class information.

## Rules

- Rule 31 records the backlink overview as an informational finding and flags a zero-domain profile as an opportunity.
- Rule 77 reports lost followed links from authoritative source pages that target crawl-relevant URLs. The check is partial if the API result is truncated or one Semrush family fails.
- Domain-keyword and competitor evidence supplements the Master Audit keyword mapping, cannibalization, ranking-change, and strategy review workflows without converting strategic/manual decisions into automatic PASS results.

No live success is claimed without a paid, authorized Semrush key with the required entitlements. Offline request and rule contracts are sufficient to complete implementation while retaining `LIVE_VALIDATION_PENDING`.
