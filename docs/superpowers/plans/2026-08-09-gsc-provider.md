# Google Search Console provider implementation plan

1. Write failing client tests for OAuth headers, encoded properties, pagination, caching, and sanitized errors.
2. Implement the shared GSC REST client.
3. Write failing provider tests for configuration, deterministic sampling, enrichment, partial success, and runner source aliases.
4. Implement and register the V3 provider.
5. Write failing rule tests for Rules 44, 52, 75, and 76, including unavailable and partial evidence.
6. Implement checks and adapter bindings; update only classifications whose executable acceptance criteria are supported.
7. Run focused tests, the complete suite, secret scans, and document live-validation status.
