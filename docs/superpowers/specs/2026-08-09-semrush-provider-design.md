# Semrush provider design

## Outcome

Add a bounded Semrush Backlinks API v4 provider for backlink inventory and important lost-link evidence. The provider must never leak API keys or consume units more than once for identical audit requests.

## API boundary

- `GET /apis/v4/backlinks/v1/overview` for aggregate backlink, referring-domain, new/lost, follow, and Authority Score metrics.
- `GET /apis/v4/backlinks/v1/links` with `is_lost = true`, explicit fields, Authority Score ordering, and a bounded result limit.
- Authentication uses `Authorization: Apikey ...`; keys remain process-only.
- The v4 API is early access, so response validation and typed failures isolate contract drift.

## Runtime and truth semantics

`MASTER_AUDIT_SEMRUSH_ENABLED`, `SEMRUSH_API_KEY`, `SEMRUSH_TARGET`, and `SEMRUSH_LOST_LINK_LIMIT` configure the provider. The target defaults to the audit base URL when not explicitly configured. Identical requests use a session cache.

Both API families are attempted independently. A successful family is preserved when the other fails. Zero successful families remove `Semrush API` from available sources. Exceptions contain only status and class information.

## Rules

- Rule 31 records the backlink overview as an informational finding and flags a zero-domain profile as an opportunity.
- Rule 77 reports lost followed links from authoritative source pages that target crawl-relevant URLs. The check is partial if the API result is truncated or one Semrush family fails.

No live success is claimed without a paid, authorized Semrush v4 key. Offline request and rule contracts are sufficient to complete implementation while retaining `LIVE_VALIDATION_PENDING`.
