# GA4 provider implementation plan

1. TDD the Admin/Data REST client: property lookup, key-event pagination, report shapes, caching, and sanitized failures.
2. TDD and implement provider configuration, property normalization, four isolated evidence families, and runner registration.
3. TDD Rules 34 and 35 for healthy, missing, zero-event, partial, and unavailable evidence.
4. Bind checks, migrate source-of-truth classifications, and update runtime configuration.
5. Run focused/full regressions, validate handoff JSON/CSV, scan for credentials, and record live-validation status.
